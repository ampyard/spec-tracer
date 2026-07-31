import pytest

from spec_tracer.collectors import FileCollector


@pytest.mark.parametrize("tag", ["@scenario:FC-004"])
def test_feature_files_collects_single_file(tag, tmp_path):
    feature = tmp_path / "a.feature"
    feature.write_text("Feature: A", encoding="utf-8")

    files = FileCollector.feature_files([str(feature)])

    assert files == [feature.resolve()]


@pytest.mark.parametrize("tag", ["@scenario:FC-004"])
def test_feature_files_recurses_into_directory(tag, tmp_path):
    (tmp_path / "sub").mkdir()
    a = tmp_path / "a.feature"
    b = tmp_path / "sub" / "b.feature"
    a.write_text("Feature: A", encoding="utf-8")
    b.write_text("Feature: B", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    files = FileCollector.feature_files([str(tmp_path)])

    assert files == sorted([a.resolve(), b.resolve()])


@pytest.mark.parametrize("tag", ["@scenario:FC-004"])
def test_feature_files_raises_when_path_does_not_exist(tag, tmp_path):
    missing = tmp_path / "missing.feature"

    with pytest.raises(FileNotFoundError):
        FileCollector.feature_files([str(missing)])


@pytest.mark.parametrize("tag", ["@scenario:FC-004"])
def test_feature_files_deduplicates_repeated_paths(tag, tmp_path):
    feature = tmp_path / "a.feature"
    feature.write_text("Feature: A", encoding="utf-8")

    files = FileCollector.feature_files([str(feature), str(feature)])

    assert files == [feature.resolve()]


@pytest.mark.parametrize("tag", ["@scenario:FC-004"])
def test_xml_files_collects_from_directory_and_skips_missing_paths(tag, tmp_path):
    xml = tmp_path / "result.xml"
    xml.write_text("<testsuite/>", encoding="utf-8")
    missing = tmp_path / "does-not-exist"

    files = FileCollector.xml_files([str(tmp_path), str(missing)])

    assert files == [xml.resolve()]


@pytest.mark.parametrize("tag", ["@scenario:FC-004"])
def test_json_files_collects_from_directory_and_skips_missing_paths(tag, tmp_path):
    payload = tmp_path / "result.json"
    payload.write_text("[]", encoding="utf-8")
    missing = tmp_path / "does-not-exist"

    files = FileCollector.json_files([str(tmp_path), str(missing)])

    assert files == [payload.resolve()]
