from prometheus_client import Counter, make_asgi_app

received_commands = Counter('commands_received', 'Count number of commands received.', ['command', ])
completed_commands = Counter('commands_completed', 'Count number of commands completed.', ['command', ])
errored_commands = Counter('commands_errored', 'Count number of commands errored.', ['command', ])

metrics_app = make_asgi_app()
