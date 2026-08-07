import json

from hermit.actions import parse_action, ListFiles, DeleteFiles, ReadFile, CreateDirectory, RunCommand


def test_parse_list_files_action():
    action = parse_action(json.dumps({"action": "list_files", "path": ".", "all": True, "long": True}))
    assert isinstance(action, ListFiles)
    assert action.render() == "ls -al ."


def test_parse_delete_files_action_with_pattern():
    action = parse_action(json.dumps({
        "action": "delete_files", "path": ".", "pattern": "*.log", "recursive": True,
    }))
    assert isinstance(action, DeleteFiles)
    assert action.render() == "find . -name '*.log' -delete"


def test_parse_read_file_action():
    action = parse_action(json.dumps({"action": "read_file", "path": "welcome.txt"}))
    assert isinstance(action, ReadFile)
    assert action.render() == "cat welcome.txt"
    assert "welcome.txt" in action.describe()


def test_parse_create_directory_action():
    action = parse_action(json.dumps({"action": "create_directory", "path": "new_folder"}))
    assert isinstance(action, CreateDirectory)
    assert action.render() == "mkdir -p new_folder"


def test_unknown_action_falls_back_to_run_command():
    action = parse_action(json.dumps({"action": "does_not_exist", "command": "echo hi"}))
    assert isinstance(action, RunCommand)


def test_invalid_json_falls_back_to_run_command_with_raw_string():
    raw = "not valid json"
    action = parse_action(raw)
    assert isinstance(action, RunCommand)
    assert action.command == raw


def test_create_file_escapes_single_quotes():
    from hermit.actions import CreateFile
    action = CreateFile(path="out.txt", content="it's a test")
    assert action.render() == "echo 'it'\\''s a test' > out.txt"
