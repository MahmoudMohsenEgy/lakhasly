from explainer import cli

def test_cli_builds_agent_and_runs(monkeypatch, tmp_path):
    captured = {}
    class FakeAgent:
        def run(self, ref, source_type="auto"):
            captured["ref"] = ref
            class S: pdf_path = str(tmp_path / "study.pdf"); errors = []
            return S()
    monkeypatch.setattr(cli, "build_agent", lambda cfg: FakeAgent())
    monkeypatch.setattr(cli.Config, "from_env",
        classmethod(lambda c: cli.Config(azure_endpoint="x", azure_deployment="d")))
    assert cli.main(["tests/fixtures/sample.txt"]) == 0
    assert captured["ref"] == "tests/fixtures/sample.txt"
