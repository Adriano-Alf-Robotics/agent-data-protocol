# ADP Plugin per Claude Code

Plugin che integra **ADP** (Adriano Dal Pastro format) in Claude Code:
skill, slash command, subagent dedicato, hook contestuale.

ADP è un formato testuale di serializzazione lossless e
token-efficient per la comunicazione tra agenti AI. Vedi
[README principale](../README.md) per la spec, i benchmark e le API.

## Cosa fornisce il plugin

| Componente | Cosa attiva | Dove |
|---|---|---|
| **Skill `adp`** | istruzione contestuale: quando serializzi dati strutturati usa ADP, non JSON | `skills/adp/SKILL.md` |
| **Subagent `adp-agent`** | task delegabile che risponde *sempre* in ADP | `agents/adp-agent.md` |
| **9 slash command** | `/adp-encode`, `/adp-decode`, `/adp-to-md`, `/adp-to-html`, `/adp-bench`, `/adp-sign`, `/adp-verify`, `/adp-serve`, `/adp-prompt` | `commands/*.md` |
| **Hook SessionStart** | annota i progetti ADP all'avvio sessione | `hooks/session-start.sh` |

## Prerequisiti

La CLI `adp` deve essere installata e raggiungibile. Due opzioni:

```bash
# Opzione A: nello stesso repo
cd /path/to/GoalLanguageAgents
uv sync --all-extras
# i comandi useranno: uv run --directory /path/to/GoalLanguageAgents adp ...

# Opzione B: globale via pip / pipx
pipx install /path/to/GoalLanguageAgents
# i comandi useranno: adp ...
```

## Installazione del plugin

### Metodo 1 — link simbolico (sviluppo)

```bash
mkdir -p ~/.claude/plugins/cache/local
ln -sf /path/to/GoalLanguageAgents/claude-plugin \
       ~/.claude/plugins/cache/local/adp
```

Modifica `~/.claude/plugins/installed_plugins.json` aggiungendo:

```json
{
  "local/adp": "0.2.0"
}
```

### Metodo 2 — copia diretta

```bash
mkdir -p ~/.claude/plugins/cache/adp/0.2.0
cp -r /path/to/GoalLanguageAgents/claude-plugin/* \
      ~/.claude/plugins/cache/adp/0.2.0/
```

### Metodo 3 — script automatico

```bash
bash /path/to/GoalLanguageAgents/claude-plugin/install.sh
```

## Verifica

Apri una nuova sessione Claude Code e controlla:

```
/adp-encode    # dovrebbe apparire fra i comandi disponibili
```

Oppure chiedi a Claude Code:

> Mostrami la skill `adp` e l'agent `adp-agent`.

## Disinstallazione

```bash
rm ~/.claude/plugins/cache/local/adp        # se link simbolico
# oppure
rm -rf ~/.claude/plugins/cache/adp           # se copia diretta
```

Rimuovi anche la voce da `~/.claude/plugins/installed_plugins.json`.

## Aggiornamenti

Se hai installato via link simbolico (metodo 1), basta aggiornare il
repository ADP — il plugin segue automaticamente.

Per copia diretta, ri-esegui `install.sh` o aggiorna manualmente.

## Caso d'uso tipico

```
> Estrai dal file customers.csv una lista di utenti con id, name, email,
> in ADP.

Claude Code → invoca il subagent adp-agent →
adp-agent ritorna:
  users=#id,name,email|1i,Alice,alice@x.io|2,Bob,bob@x.io|3,Carla,carla@x.io

Claude Code → mostra la stringa, suggerisce di salvarla con Write o di
              decodificarla con /adp-decode.
```

## Licenza

MIT, vedi `LICENSE` nel repository principale.
