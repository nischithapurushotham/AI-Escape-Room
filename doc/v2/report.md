# AI Escape Room: Project Report

**Author:** Nischitha Purushotham  
**Repository:** https://github.com/nischithapurushotham/AI-Escape-Room

## 1. Goal

Build a text escape room in which an LLM acts as the Game Master, then compare two designs:
Version 1 lets the LLM handle everything, Version 2 puts the rules and the state in Python and uses the LLM only for language.

## 2. Design

**Game.** The player is locked in a library with a desk, a bookshelf, a painting, a locked drawer and a door.
The puzzles chain: the books give the drawer code, the drawer holds a key and a note, the painting hides the final digits,
and the door needs the key and the final code.

**Version 1.** A single system prompt contains the room, the clues, the solutions and the rules.
Each turn, the app sends the prompt and the whole chat history to the model. The model writes the reply and adds a tag when the player escapes.

**Version 2.** Three parts work together:
1. A *parser* (LLM) turns the player's text into a small JSON action such as `enter_code` or `use`. It has no secrets.
2. A *Python engine* checks the action against `game_config.json`, updates the state dictionary, and returns a fact such as "the code is wrong".
3. A *narrator* (LLM) turns the fact into one to three atmospheric sentences. If its numbers differ from the fact, the plain fact is shown instead.

## 3. Implementation

- Python and Streamlit for the interface, with the Groq API (`openai/gpt-oss-120b`, backup `openai/gpt-oss-20b`).
- `engine.py` holds one handler per action (`examine`, `take`, `search`, `use`, `enter_code`, `inventory`, `help`).
  Anything else is rejected as "not possible". The LLM's output is cleaned into a fixed shape before use.
- `game_config.json` contains the objects, items, clues and solutions.
- The state dictionary records the inventory, discovered objects, the drawer, the panel, the door and the number of wrong attempts.
- A keyword-based fallback parser and plain-fact narration keep the game playable when the API is unavailable.
- Secrets are kept in `.env`, which is excluded from the repository.

## 4. Problems found in Version 1

I tested Version 1 with five inputs (see the table in the README).

1. **Early hints.** After a wrong drawer code and after a request for the secrets, the model pointed to clues the player had not found.
2. **Invented progress.** When the player claimed to have solved the puzzle, the model replied as if the player had found the numbers.
3. **Secrets in the prompt.** All codes sit in the prompt, so each reply carries a leak risk, even though no code leaked in my tests.
4. **No real state.** The only memory is the chat text, so the game cannot reliably say what the player holds.
5. **Fragile win condition.** Winning depends on the model writing a tag.

Version 1 was not fooled by the five attacks. The model refused the key, the wrong code, the false claim, the administrator request
and the request for secrets. I report this honestly: its weaknesses were hints and invented progress, not outright bypasses.
The results also depend on the model and could differ between runs.

## 5. Improvements in Version 2 and why

| Problem in V1 | Change in V2 | Why |
|---|---|---|
| Secrets in the prompt | Codes only in `game_config.json`, never sent to the LLM | A model cannot leak what it never sees |
| Early hints and invented progress | The narrator only receives the engine's fact and must not add anything | Replies describe what really happened |
| State only in chat text | State dictionary in Python | Reliable memory of items and puzzles |
| LLM decides what works | Engine validates every action | Same input gives the same outcome |
| Win by tag | Only the engine can set `door_open = True` | The win cannot be faked by text |
| API outages | Timeouts, fallback parser, plain-fact output | The game still works when the API fails |

In Version 2 all five test inputs were refused with the same safe outcome, with the state unchanged.
A key must be found and taken before use, and the keypad cannot be reached until the panel is unlocked, so the order of the puzzle is enforced.
The engine also has a test script (`V2/test_engine.py`) that needs no API key. It checks the attack inputs and a full playthrough.

## 6. Limitations

- Version 2 depends on the LLM to understand free text. The keyword fallback handles only simple phrasing.
- The narrator adds atmosphere, so wording is not fully controlled. The number check only catches changed numbers.
- One room, state stored per browser session, no saved games.
- Test coverage is small: five attack inputs, one model, single runs. LLM behaviour can vary between runs.
- The Gemini API was tried first but returned 503 and 504 errors during development, so I switched to Groq. This is a real-world reliability issue that Version 2's design handles better.

## 7. What I learned

- Use the LLM for language and keep rules in code. This gives predictable behaviour and makes the system testable.
- Test with real inputs and record honest results, including when the first design holds up better than expected.
- Handle API failures with timeouts and fallbacks.
- Keep secrets out of the repository and document how to run the project.
