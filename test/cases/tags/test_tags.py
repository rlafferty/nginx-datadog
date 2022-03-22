from .. import case

import json
from pathlib import Path


def parse_trace(log_line):
    """Return a trace (list of list of dict) parsed from the specified
    `log_line`, or return `None` if `log_line` is not a trace.
    """
    try:
        return json.loads(log_line)
    except json.decoder.JSONDecodeError:
        return None


class TestTags(case.TestCase):
    def run_custom_tags_test(self, conf_relative_path):
        """Verify that spans produced by an nginx configured using the
        specified nginx `conf_text` (from a file having the specified
        `file_name`) contain expected values for the "snazzy.tag" and
        "fancy.tag" tags.
        """
        conf_path = Path(__file__).parent / conf_relative_path
        conf_text = conf_path.read_text()
        # To test this, we make any old request to nginx, and then in order
        # to ensure that nginx flushes its trace to the agent, reload nginx.
        # Then we send a "sync" request to the agent in order to establish a
        # log line that's strictly after the trace was flushed, and finally we
        # examine the interim log lines from the agent to find the tags sent to
        # it by nginx's tracer.
        self.orch.nginx_replace_config(conf_text, conf_path.name)

        # Consume any previous logging from the agent.
        self.orch.sync_service('agent')

        status, _ = self.orch.send_nginx_http_request('/http')
        self.assertEqual(status, 200, conf_relative_path)

        self.orch.reload_nginx()
        log_lines = self.orch.sync_service('agent')

        for line in log_lines:
            segments = parse_trace(line)
            if segments is None:
                # some other kind of logging; ignore
                continue
            for segment in segments:
                for span in segment:
                    if span['service'] != 'nginx':
                        continue
                    # We found an nginx span.  Make sure that it has the
                    # "snazzy.tag" and "fancy.tag" tags, with the expected values.
                    # The two tags are assumed to be configured in `conf_text`.
                    tags = span['meta']

                    self.assertIn('snazzy.tag', tags, conf_relative_path)
                    self.assertEqual(tags['snazzy.tag'], 'hard-coded',
                                     conf_relative_path)

                    self.assertIn('fancy.tag', tags, conf_relative_path)
                    self.assertEqual(tags['fancy.tag'], 'GET',
                                     conf_relative_path)

    def test_custom_in_location(self):
        return self.run_custom_tags_test('./conf/custom_in_location.conf')

    def test_custom_in_server(self):
        return self.run_custom_tags_test('./conf/custom_in_server.conf')

    def test_custom_in_http(self):
        return self.run_custom_tags_test('./conf/custom_in_http.conf')

    def test_default_tags(self):
        # We want to make sure that when nginx produces a span,
        # it contains the builtin tags.
        # To test this, we make any old request to nginx, and then in order
        # to ensure that nginx flushes its trace to the agent, reload nginx.
        # Then we send a "sync" request to the agent in order to establish a
        # log line that's strictly after the trace was flushed, and finally we
        # examine the interim log lines from the agent to find the tags sent to
        # it by nginx's tracer.
        conf_path = Path(__file__).parent / './conf/builtins.conf'
        conf_text = conf_path.read_text()
        self.orch.nginx_replace_config(conf_text, conf_path.name)

        # Consume any previous logging from the agent.
        self.orch.sync_service('agent')

        status, _ = self.orch.send_nginx_http_request('/http')
        self.assertEqual(status, 200)

        self.orch.reload_nginx()
        log_lines = self.orch.sync_service('agent')

        for line in log_lines:
            segments = parse_trace(line)
            if segments is None:
                # some other kind of logging; ignore
                continue
            for segment in segments:
                for span in segment:
                    if span['service'] != 'nginx':
                        continue
                    # Here's a span that nginx sent.  Make sure it has the default tags.
                    # These tag names come from `TracingLibrary::default_tags` in
                    # `tracing_library.cpp`.
                    # Some of the span values are easy to predict, while for
                    # others we just check that the tag is present.
                    tags = span['meta']

                    self.assertIn('component', tags)
                    self.assertEqual(tags['component'], 'nginx')

                    self.assertIn('nginx.worker_pid', tags)
                    int(tags['nginx.worker_pid'])

                    self.assertIn('peer.address', tags)

                    self.assertIn('upstream.address', tags)

                    self.assertIn('http.method', tags)
                    self.assertEqual(tags['http.method'], 'GET')

                    self.assertIn('http.url', tags)

                    self.assertIn('http.host', tags)

                    self.assertIn('http_user_agent', tags)
