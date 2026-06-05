import argparse, sys
from explainer.config import Config
from explainer.composition import build_agent

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="explain",
        description="Generate an Egyptian-Arabic study PDF from English content.")
    parser.add_argument("source", help="Path or URL: .txt/.md/.pdf/.vtt/.srt or http(s)://")
    parser.add_argument("--out", default=None, help="Output directory")
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.out:
        config.output_dir = args.out

    agent = build_agent(config)
    state = agent.run(args.source)
    for e in state.errors:
        print(f"WARNING: {e}", file=sys.stderr)
    if state.pdf_path:
        print(f"Done. PDF: {state.pdf_path}")
        return 0
    print("Failed: no PDF produced.", file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
