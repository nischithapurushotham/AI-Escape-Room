# Architecture diagrams

GitHub renders these Mermaid diagrams directly. To get PNG images for the report,
paste each block (without the ```mermaid lines) into https://mermaid.live and download the image.

## Version 1: the LLM does everything

```mermaid
flowchart LR
    P[Player] -->|types a message| UI[Streamlit chat UI]
    UI -->|system prompt with ALL secrets<br/>plus the full chat history| LLM[LLM Game Master]
    LLM -->|reply text, may contain the tag ESCAPED| UI
    UI -->|shows reply, detects the tag| P
```

The LLM holds the codes, decides what works, and is the only memory of the game.
Weak points: it can leak the codes, forget earlier actions, invent objects, and be talked into anything.

## Version 2: Python owns the rules, the LLM only talks

```mermaid
flowchart LR
    P[Player] -->|types a message| UI[Streamlit chat UI]
    UI -->|player text only, no secrets| PA[LLM parser<br/>text to JSON intent]
    PA -->|intent| EN[Python engine<br/>validates every action]
    CFG[(game_config.json<br/>rules and solutions)] --> EN
    EN <-->|reads and updates| ST[(Game state<br/>inventory, revealed, drawer,<br/>panel, door)]
    EN -->|FACT: what really happened| NA[LLM narrator<br/>describes the fact]
    NA -->|story text| CK[Output check<br/>numbers must match the fact]
    CK -->|safe text| UI
    UI -->|shows reply and inventory| P
    PA -.->|LLM down| FB[Keyword fallback parser]
    FB -.-> EN
```

The LLM never sees the codes and cannot change the game state.
Only the Python engine can set `door_open = True`.
If the LLM is down, a keyword parser and plain facts keep the game playable.
