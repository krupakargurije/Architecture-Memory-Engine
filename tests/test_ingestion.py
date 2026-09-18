from pathlib import Path
from ame.ingestion.local_git import LocalGitIngestion
from ame.ingestion.ide_stream import IDEStreamIngestion
from ame.security.filter import SecurityFilter


def test_security_filter_excludes_secrets():
    sf = SecurityFilter()

    # Secret files must be rejected
    safe, reason = sf.is_safe_to_index(Path(".env"))
    assert not safe
    assert "sensitive/secret" in reason

    safe, reason = sf.is_safe_to_index(Path("credentials.json"))
    assert not safe

    safe, reason = sf.is_safe_to_index(Path("src/private.pem"))
    assert not safe

    # Standard java / python file inside allowed path must pass
    safe, reason = sf.is_safe_to_index(Path("src/main/OrderService.java"))
    assert safe
    assert reason is None

    safe, reason = sf.is_safe_to_index(Path("app/main.py"))
    assert safe


def test_local_ingestion_and_ide_stream(tmp_path):
    # Create temporary repo directory
    sample_file = tmp_path / "UserService.java"
    sample_file.write_text("public class UserService {}", encoding="utf-8")

    ingestion = LocalGitIngestion()
    norm_repo = ingestion.ingest(str(tmp_path), repo_id="test-repo")

    assert norm_repo.repo_id == "test-repo"
    assert "UserService.java" in norm_repo.files
    assert norm_repo.snapshot is not None

    # Test IDE uncommitted streaming
    ide_stream = IDEStreamIngestion()
    stream_repo = ide_stream.ingest(
        target=str(tmp_path),
        repo_id="test-repo",
        uncommitted_buffers={"PaymentService.java": "public class PaymentService {}"}
    )
    assert stream_repo.snapshot.is_dirty
    assert "PaymentService.java" in stream_repo.files
