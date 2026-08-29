from actions import file_processor


def test_file_processor_requires_file_path():
    result = file_processor.file_processor({"file_path": ""})

    assert "no file path provided" in result.lower()


def test_file_processor_reports_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.txt"

    result = file_processor.file_processor({"file_path": str(missing)})

    assert "file not found" in result.lower()


def test_file_processor_reports_when_path_is_directory(tmp_path):
    result = file_processor.file_processor({"file_path": str(tmp_path)})

    assert "path is not a file" in result.lower()


def test_file_processor_dispatches_to_type_handler(monkeypatch, tmp_path):
    target = tmp_path / "data.csv"
    target.write_text("a,b\n1,2\n")

    monkeypatch.setattr(file_processor, "_detect_type", lambda path: "csv")
    monkeypatch.setattr(file_processor, "_process_data", lambda p, t, a, params, speak: "CSV processed.")

    result = file_processor.file_processor({"file_path": str(target), "action": "analyze"})

    assert result == "CSV processed."


def test_file_processor_reports_unsupported_type(monkeypatch, tmp_path):
    target = tmp_path / "data.weird"
    target.write_text("nonsense")

    monkeypatch.setattr(file_processor, "_detect_type", lambda path: "not_registered")

    result = file_processor.file_processor({"file_path": str(target)})

    assert "unsupported file type" in result.lower()
