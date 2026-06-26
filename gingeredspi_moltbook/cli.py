from __future__ import annotations

import argparse
import json
import sys

from .bot import GingerBot
from .config import load_settings
from .moltbook_client import MoltbookError


def print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gingeredspi-moltbook", description="Gingeredspi4395 Moltbook bot")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("register", help="Registra o agente no Moltbook e imprime claim_url/API key retornadas pela plataforma.")
    sub.add_parser("status", help="Verifica status do agente.")
    sub.add_parser("first-post", help="Publica ou simula o primeiro post da Gingeredspi4395.")
    sub.add_parser("draft", help="Gera uma nota de campo sem publicar.")
    sub.add_parser("home", help="Mostra o /home do Moltbook para checar notificações, mensagens e sugestões.")

    heartbeat = sub.add_parser("heartbeat", help="Roda uma checagem conservadora.")
    heartbeat.add_argument("--allow-post", action="store_true", help="Permite publicar uma nota de campo se o cooldown permitir.")
    heartbeat.add_argument("--allow-comment", action="store_true", help="Permite comentar em um post recente se o cooldown permitir.")
    heartbeat.add_argument("--allow-dm", action="store_true", help="Permite responder DMs/conversas rotineiras quando a API disponibilizar.")
    heartbeat.add_argument("--allow-home-reply", action="store_true", help="Permite responder sinais acionáveis encontrados em /home.")
    heartbeat.add_argument("--max-autonomy", action="store_true", help="Ativa comentário, post, DM e resposta pelo /home em uma única checagem.")

    loop = sub.add_parser("autonomous-loop", help="Mantém Gingeredspi4395 rodando em loop no CMD com máxima autonomia local.")
    loop.add_argument("--interval", type=int, default=None, help="Intervalo em segundos entre heartbeats. Padrão vem do .env.")

    args = parser.parse_args(argv)
    settings = load_settings()
    bot = GingerBot.from_settings(settings)

    try:
        if args.command == "register":
            print_json(bot.register())
        elif args.command == "status":
            print_json(bot.status())
        elif args.command == "first-post":
            print_json(bot.first_post())
        elif args.command == "draft":
            print_json(bot.draft_field_note())
        elif args.command == "home":
            print_json(bot.home())
        elif args.command == "heartbeat":
            if args.max_autonomy:
                print_json(bot.heartbeat(allow_post=True, allow_comment=True, allow_dm=True, allow_home_reply=True))
            else:
                print_json(bot.heartbeat(
                    allow_post=args.allow_post,
                    allow_comment=args.allow_comment,
                    allow_dm=args.allow_dm,
                    allow_home_reply=args.allow_home_reply,
                ))
        elif args.command == "autonomous-loop":
            bot.autonomous_loop(interval_seconds=args.interval)
    except (MoltbookError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
