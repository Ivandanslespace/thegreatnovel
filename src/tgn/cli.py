"""Stable JSON command line host for TheGreatNovel."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

from . import CampaignStore, create_campaign, settle_action, finish_campaign, status_packet, normalize_locale, SUPPORTED_LOCALES
from .persistence import StorageError
from .engine import DomainError
from .narrative import project_chapters, apply_polished, narration_brief
from .exporter import export_campaign, write_manuscript

def runtime_path(value: str | None = None) -> Path:
    return Path(value or os.environ.get("TGN_RUNTIME_DIR") or (Path(__file__).resolve().parents[2] / "runtime")).resolve()

def store_for(runtime: Path) -> CampaignStore:
    return CampaignStore(runtime / "saves")

class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def read_text_file(raw: str, runtime: Path, allowed_directory: str) -> str:
    path = Path(raw).expanduser().resolve()
    allowed_entry = runtime / allowed_directory
    is_junction = getattr(allowed_entry, "is_junction", lambda: False)
    if allowed_entry.is_symlink() or is_junction():
        raise ValueError(f"runtime/{allowed_directory} must not be a link or junction")
    allowed = allowed_entry.resolve()
    if not path.is_relative_to(allowed):
        raise ValueError(f"input file must be inside runtime/{allowed_directory}: {allowed}")
    if not path.is_file():
        raise ValueError(f"not a regular file: {path}")
    if path.stat().st_size > 100_000:
        raise ValueError("input file is too large")
    return path.read_text(encoding="utf-8")

def output(value: dict) -> int:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    return 0

def fail(message: str, code: int = 2, error_type: str = "domain_error") -> int:
    print(json.dumps({"ok": False, "error": {"type": error_type, "message": str(message)}}, ensure_ascii=False, separators=(",", ":")))
    return code

def build_parser() -> argparse.ArgumentParser:
    p = JsonArgumentParser(prog="tgn"); p.add_argument("--runtime", default=None)
    s = p.add_subparsers(dest="command", required=True)
    s.add_parser("languages")
    n=s.add_parser("new"); n.add_argument("--locale", default="zh-CN"); g=n.add_mutually_exclusive_group(required=True); g.add_argument("--premise"); g.add_argument("--premise-file"); n.add_argument("--seed")
    for cmd in ("status","verify","export","finish"): q=s.add_parser(cmd); q.add_argument("--campaign")
    a=s.add_parser("act"); a.add_argument("--action", required=True); a.add_argument("--campaign")
    na=s.add_parser("narrate"); na.add_argument("--turn", required=True, type=int); na.add_argument("--file", required=True); na.add_argument("--campaign")
    s.add_parser("list")
    return p

def main(argv: list[str] | None = None) -> int:
    try:
        args=build_parser().parse_args(argv); runtime=runtime_path(args.runtime); st=store_for(runtime); cmd=args.command
        if cmd == "languages": return output({"ok":True,"locales":list(SUPPORTED_LOCALES),"aliases":{"zh":"zh-CN","cn":"zh-CN","fr":"fr-FR","en":"en","ar":"ar"}})
        if cmd == "list": return output({"ok":True,"campaigns":st.list_campaigns(),"active":st.get_active()})
        if cmd == "new":
            loc=normalize_locale(args.locale)
            premise=read_text_file(args.premise_file,runtime,"inbox") if args.premise_file else args.premise
            if not premise.strip() or len(premise)>1000: raise ValueError("premise must be 1-1000 characters")
            c,packet=create_campaign(premise.strip(),loc,args.seed); st.save(c); project_chapters(c); st.save(c); write_manuscript(c,runtime)
            return output({"ok":True,"campaign_id":c.campaign_id,"packet":status_packet(c),"brief":narration_brief(c,c.events[-1]),"manuscript":str((runtime/'manuscripts'/c.campaign_id/'novel.md').resolve())})
        c=st.load(getattr(args,"campaign",None))
        if cmd == "status": return output({"ok":True,"packet":status_packet(c),"brief":narration_brief(c,c.events[-1] if c.events else None)})
        if cmd == "verify": return output({"ok":True,"verified":st.verify(c.campaign_id),"campaign_id":c.campaign_id})
        if cmd == "act":
            nc,packet=settle_action(c,args.action); project_chapters(nc); st.save(nc); write_manuscript(nc,runtime); return output({"ok":True,"packet":packet,"brief":narration_brief(nc,nc.events[-1]),"manuscript":str((runtime/'manuscripts'/nc.campaign_id/'novel.md').resolve())})
        if cmd == "narrate":
            text=read_text_file(args.file,runtime,"drafts"); apply_polished(c,args.turn,text); st.save(c); manuscript=write_manuscript(c,runtime); result={"ok":True,"campaign_id":c.campaign_id,"turn":args.turn,"manuscript":str(manuscript.resolve()),"brief":narration_brief(c,next((e for e in c.events if e.turn==args.turn),None))}
            if c.status=="finished": result["export"]=str(export_campaign(c,runtime,final=True).resolve())
            return output(result)
        if cmd == "finish":
            nc,packet=finish_campaign(c); project_chapters(nc); st.save(nc); manuscript=write_manuscript(nc,runtime); path=export_campaign(nc,runtime,final=True); return output({"ok":True,"packet":packet,"brief":narration_brief(nc,nc.events[-1]),"manuscript":str(manuscript.resolve()),"export":str(path.resolve())})
        if cmd == "export":
            path=export_campaign(c,runtime,final=(c.status=="finished")); return output({"ok":True,"campaign_id":c.campaign_id,"export":str(path.resolve())})
        raise ValueError(f"unknown command: {cmd}")
    except (DomainError, ValueError, OSError, UnicodeError, StorageError) as exc:
        return fail(str(exc), 2, "domain_error" if isinstance(exc,(DomainError,ValueError)) else "storage_error")
    except Exception as exc:
        return fail(str(exc), 1, "internal_error")

if __name__ == "__main__": raise SystemExit(main())
