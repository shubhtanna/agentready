# AgentReady agents (Fetch.ai)

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

Fetch.ai uAgents for AgentReady, built for Fetch-A-Thon 3.0. They speak the
Agent Chat Protocol, so they can be used from ASI:One.

| Agent | What it does | Address |
|---|---|---|
| **AgentReady** | Scans a website and explains how well AI shopping agents can find, read and buy from it | `agent1qwl5c4d77prydcy4skseaktuwquy6qwdp68fv5fqrkdgfvx3ph9uc6w8a2v` (local dev seed) |
| **AgentReady Tester** | Actually tries to shop on a website like an AI agent (find, compare, add to cart, get a checkout link) and reports each step | `agent1qvxkjpe6z7gnheuzqhf6hp6cuwld7serzjuhktyvdph9cgn3vgf6zw3zv2e` (local dev seed) |
| **AgentReady Fixer** | Changes the store's code on GitHub so agents can buy, proves it with a before/after Tester run, and opens a pull request | `agent1q2y3q9z0y3dd3rj4m5ajgu5vpkv6gwaff2h2jd52yhx3l6demp0lxnaq9sd` (local dev seed) |

## How the Fixer works

In ASI:One: `Fix voltkart.onrender.com, code at github.com/you/your-store` → a fix plan → `apply all` (or `apply 1,3`) → a pull request → after merging, `retest`.

1. **Diagnose.** Clones the repo, detects the stack (Next.js, Vite SPA, Node/Express, Flask, Django, plain HTML) and runs the Tester on the live site.
2. **Plan.** Maps failed steps to generic fixes (`fixer_agent/playbook.py`): robots.txt access for AI agents, products readable without JavaScript, JSON-LD + sitemap + llms.txt, plain-HTML add to cart, and a checkout link that carries the cart. Nothing is store-specific.
3. **Fix.** ASI:One (`asi1`, tool calling) edits the repo through a few safe tools: list, read, search, write, replace, build, test. It cannot run commands, edit secrets, lockfiles or git, or touch anything outside the repo.
4. **Prove.** The original and the patched store are installed, built and run locally, and the Tester shops on both. Failing steps are fed back for up to three rounds.
5. **Pull request** with the before/after table. Nothing is merged or deployed.

It only works on repos listed in `FIXER_ALLOWED_REPOS`, whoever asks. Running a repo's install and build executes its code, so in production this should run in a sandbox.

```bash
python tools/run_fixer.py voltkart.onrender.com github.com/you/voltkart-store "wireless earbuds under ₹10,000"                 # plan only
python tools/run_fixer.py voltkart.onrender.com github.com/you/voltkart-store "wireless earbuds under ₹10,000" --apply all --dry # fix + test, no PR
python tools/local_fixer_chat.py "Fix github.com/you/voltkart-store for earbuds" "apply all"                                     # chat locally
```

## How the Tester works

It reads a site the way most AI agents do, as plain HTML with no JavaScript, keeping cookies only for its own session and honouring `robots.txt`. Nothing in it is specific to any store.

| Step | Passes when |
|---|---|
| 1. Reach the site | The homepage has readable content without JavaScript |
| 2. Find products | Products matching the request can be read from links, sitemap, `llms.txt` or structured data |
| 3. Compare options | At least two matches have a readable name and price |
| 4. Add to cart | The product lands in a cart through something the site exposes (an agent API or a plain HTML form) and `robots.txt` allows it |
| 5. Checkout link | A link opened by the human, with no agent cookies, shows a checkout containing the chosen product |

```bash
python tools/run_tester.py https://example-store.com "running shoes under ₹10,000"
python tools/run_tester.py --demo --json results/latest.json   # all five demo stores
```

Baseline on the five demo stores (19 Oct 2026, `results/baseline-2026-10-19.json`):

| Store | Stack | Steps passed | Stops at |
|---|---|---|---|
| [Stride Lab](https://stride-lab-beta.vercel.app) | React SPA | 0/5 | Page is empty without JavaScript |
| [Nest & Grain](https://nest-and-grain.vercel.app) | Next.js | 4/5 | Cart is tied to the agent's session; checkout link opens empty for the human |
| [Masala Mandi](https://masala-mandi.onrender.com) | Flask | 4/5 | ₹299 minimum order; cart tied to the agent's session |
| [Tara Handmade](https://tara-handmade.vercel.app) | Plain HTML/JS | 1/5 | Product pages are drawn by JavaScript |
| [VoltKart](https://voltkart.onrender.com) | Node/Express | 3/5 | `robots.txt` disallows `/cart` for automated agents |

Fixer dry runs on the same stores (21 Oct 2026; local build of each repo, before and after, same Tester, no PR opened):

| Store | Stack | Before | After | What it changed |
|---|---|---|---|---|
| Stride Lab | React SPA | 0/5 | **5/5** | Build-time generator writes static product, cart and checkout pages from `products.json`; the React app still takes over in the browser |
| Nest & Grain | Next.js | 4/5 | **5/5** | Checkout accepts `?items=` and rebuilds the cart on the server; JSON-LD, sitemap, `llms.txt` |
| Masala Mandi | Flask | 4/5 | **5/5** | Shareable checkout link; ₹299 minimum still enforced when placing the order |
| Tara Handmade | Plain HTML/JS | 1/5 | **5/5** | Generator script reads `js/products.js` and writes product, cart and checkout pages |
| VoltKart | Node/Express | 3/5 | **5/5** | robots.txt lets shopping agents use the cart; checkout link carries the cart; CSRF unchanged |

After merging the five Fixer pull requests (22 Oct 2026), the Tester scores **5/5 on every live store** (`results/after-merge-2026-10-22.json`). The checkout links it handed over were then used to place demo orders as a human would: Nest & Grain `NG-MVJ6W8DN`, Masala Mandi `MM2652303`, Tara Handmade `TH342453`, Stride Lab `SL52386880` (VoltKart needs a customer account to place the order).

Sixth demo store, kept **unfixed** for live demos (24 Oct 2026): [Kitaab Corner](https://kitaab-corner.vercel.app), an Astro bookshop. The Tester scores it **1/5**: it finds the thrillers, but prices only appear after JavaScript loads them, so an agent can't tell which are under ₹500. Its bag and checkout are browser-only too.

Seventh demo store, also kept **unfixed** (25 Oct 2026): [Leaf & Loam](https://leaf-and-loam.vercel.app), a Nuxt plant nursery. The Tester scores it **1/5**: listing pages show 8 items and load the rest with a JavaScript "Load more" button, search is JavaScript-only and there's no sitemap, so an agent never finds the snake plants. Its cart is a JavaScript-only API.

## Run it locally

Requires Python 3.10+.

```bash
cd agents
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

Fill in `.env`: set `AGENTREADY_AGENT_SEED` to any long secret phrase, and `ASI1_API_KEY` to your key from [asi1.ai](https://asi1.ai/dashboard/api-keys). Without the key the agent still works, using simple address detection.

**Try a conversation without ASI:One** (runs the agent and a test client together):

```bash
python tools/local_chat_test.py "Is example.com ready for AI shoppers?"
```

**Run the agent on its own:**

```bash
python agentready_agent/agent.py
```

**Run all three agents for ASI:One** (each in its own window, connected to Agentverse):

```bash
powershell -ExecutionPolicy Bypass -File agents\start_agents.ps1
```

## Connect to Agentverse and ASI:One

1. In `.env` set `AGENT_MAILBOX=true`, then run the agent.
2. Open the **Agent inspector** link it prints and click **Connect → Mailbox**.
3. On Agentverse, set the name, handle and description, then use **Chat with Agent**.

## Files

| Path | Purpose |
|---|---|
| `agentready_agent/agent.py` | uAgent + chat protocol wiring, per-user scan limit |
| `agentready_agent/brain.py` | Understands the message (ASI:One `asi1` model, regex fallback), calls the AgentReady API, writes the reply |
| `tester_agent/agent.py` | Tester uAgent + chat protocol wiring, per-user run limit |
| `tester_agent/shopper.py` | The five shopping steps and the report |
| `tester_agent/web.py` | Plain-HTTP "browser": cookies, robots.txt, form posts |
| `tester_agent/signals.py` | Reads text, structured data, links, prices and forms from a page |
| `tools/run_tester.py` | Run the Tester from the command line |
| `tools/local_chat_test.py` | Local end-to-end chat test (`--tester` for the Tester) |
| `fixer_agent/agent.py` | Fixer uAgent + chat protocol: plan, apply, retest |
| `fixer_agent/playbook.py` | Generic fixes and how they map to failed Tester steps |
| `fixer_agent/coder.py` | ASI:One tool-calling loop that edits the repo |
| `fixer_agent/workspace.py` | Detects the stack; installs, builds and runs a store locally |
| `fixer_agent/github.py` | Clone, branch, push and pull request |
| `tools/run_fixer.py`, `tools/local_fixer_chat.py` | Run the Fixer from the command line / chat with it locally |

The agent sends `AGENT_API_KEY` to the AgentReady API so all its users don't share one IP's public scan limit. Set the same value as `AGENT_API_KEY` on the API.
