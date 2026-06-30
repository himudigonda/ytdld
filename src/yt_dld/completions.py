"""Shell completion scripts emitted by `ytdld completions <shell>`."""

from __future__ import annotations

import sys

_VERBS = "tui doctor update config completions"
_FLAGS = (
    "-i --input -o --out --mode --quality --threads --archive "
    "--cookies-from-browser --sponsorblock --no-thumbnail --no-metadata "
    "--select --dry-run --no-notify --version --help"
)

BASH = f"""# ytdld bash completion — source this or add to ~/.bashrc:
#   eval "$(ytdld completions bash)"
_ytdld() {{
  local cur verbs flags
  cur="${{COMP_WORDS[COMP_CWORD]}}"
  verbs="{_VERBS}"
  flags="{_FLAGS}"
  if [ "$COMP_CWORD" -eq 1 ]; then
    COMPREPLY=( $(compgen -W "$verbs $flags" -- "$cur") )
  else
    case "${{COMP_WORDS[COMP_CWORD-1]}}" in
      --mode) COMPREPLY=( $(compgen -W "mp3 mp4 flac" -- "$cur") ); return;;
      --quality) COMPREPLY=( $(compgen -W "best 2160p 1440p 1080p 720p 480p" -- "$cur") ); return;;
      --sponsorblock) COMPREPLY=( $(compgen -W "off mark skip" -- "$cur") ); return;;
      -i|--input|-o|--out) COMPREPLY=( $(compgen -f -- "$cur") ); return;;
    esac
    COMPREPLY=( $(compgen -W "$flags" -- "$cur") )
  fi
}}
complete -F _ytdld ytdld
"""

ZSH = f"""#compdef ytdld
# ytdld zsh completion — add to a dir on $fpath, or:
#   eval "$(ytdld completions zsh)"
_ytdld() {{
  local -a verbs flags
  verbs=({_VERBS})
  flags=({_FLAGS})
  if (( CURRENT == 2 )); then
    compadd -- $verbs $flags
  else
    case "$words[CURRENT-1]" in
      --mode) compadd mp3 mp4 flac;;
      --quality) compadd best 2160p 1440p 1080p 720p 480p;;
      --sponsorblock) compadd off mark skip;;
      *) compadd -- $flags;;
    esac
  fi
}}
compdef _ytdld ytdld
"""

FISH = """# ytdld fish completion — save to ~/.config/fish/completions/ytdld.fish, or:
#   ytdld completions fish | source
complete -c ytdld -f
complete -c ytdld -n __fish_use_subcommand -a "tui doctor update config completions"
complete -c ytdld -l mode -a "mp3 mp4 flac" -d "output format"
complete -c ytdld -l quality -a "best 2160p 1440p 1080p 720p 480p" -d "mp4 quality"
complete -c ytdld -l sponsorblock -a "off mark skip" -d "SponsorBlock"
complete -c ytdld -s i -l input -r -d "links file"
complete -c ytdld -s o -l out -r -d "output dir"
complete -c ytdld -l threads -d "parallel workers"
complete -c ytdld -l archive -d "skip already-downloaded"
complete -c ytdld -l cookies-from-browser -d "browser cookies"
complete -c ytdld -l no-thumbnail
complete -c ytdld -l no-metadata
complete -c ytdld -l select -d "interactive picker"
complete -c ytdld -l dry-run -d "list without downloading"
complete -c ytdld -l no-notify
complete -c ytdld -l version
"""

_SCRIPTS = {"bash": BASH, "zsh": ZSH, "fish": FISH}


def run_completions(argv: list[str]) -> int:
    shell = argv[0].lower() if argv else ""
    if shell not in _SCRIPTS:
        print(
            "usage: ytdld completions <bash|zsh|fish>\n\n"
            "  bash:  eval \"$(ytdld completions bash)\"\n"
            "  zsh:   eval \"$(ytdld completions zsh)\"\n"
            "  fish:  ytdld completions fish | source",
            file=sys.stderr,
        )
        return 1
    print(_SCRIPTS[shell])
    return 0
