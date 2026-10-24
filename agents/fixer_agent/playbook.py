"""What can be fixed, and how: turns a Tester report into a plan of generic fixes.

Each fix says, in plain words, what is wrong for AI shopping agents and how stores
usually solve it, with hints per stack. Nothing here knows any particular store;
the coding model adapts the fix to the repo it is working on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .workspace import Stack

STATIC_HOSTED = ("vite-spa", "static", "astro", "static-build")


@dataclass
class Fix:
    id: str
    title: str
    why: str                      # for the store owner
    steps: list[str]              # Tester steps this fix should make pass
    guidance: str                 # for the coding model
    check_first: bool = False     # may already work; earlier failures hid it


@dataclass
class Plan:
    fixes: list[Fix] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # findings the Fixer will not change

    def add(self, fix: Fix):
        if all(f.id != fix.id for f in self.fixes):
            self.fixes.append(fix)


def _robots(stack: Stack) -> Fix:
    return Fix(
        "robots", "Let AI shopping agents in (robots.txt)",
        "Your robots.txt turns away AI agents or blocks the cart, so well-behaved agents stop before they can buy.",
        ["Reach the site", "Add to cart"],
        """Edit the store's robots.txt (a static file such as public/robots.txt or static/robots.txt, or the route that
serves it, e.g. app/robots.ts in Next.js; create public/robots.txt if there is none).
- Remove the rules that block AI assistants and shopping agents: GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot,
  Claude-User, PerplexityBot. Keep blocks on pure training crawlers (CCBot, Google-Extended) as they were.
- Do not Disallow the paths an agent needs to shop: product pages, listing and search pages, the add-to-cart
  endpoint, the cart and the checkout page. Keep Disallow rules for accounts, admin, orders and internal APIs.
- Add `Sitemap: /sitemap.xml` (an absolute URL if the domain is known) when a sitemap exists or is being added.""",
    )


LISTINGS = """
- Listing and category pages must reach every product in plain HTML. If they show the first few items and load the
  rest with JavaScript ("Load more", infinite scroll), keep that for humans but add server-rendered pagination links
  (e.g. ?page=2, rendered on the server) or list every item, so each product page is linked from somewhere."""


def _readable(stack: Stack, finding: str = "") -> Fix:
    fix = _readable_fix(stack)
    if "price" in finding.lower() and "javascript" in finding.lower():
        fix.why = "Your prices only appear after JavaScript runs, so an agent can't see what anything costs or keep to a budget."
    elif "load more" in finding.lower():
        fix.why = "Most of your products are only reachable through a JavaScript “Load more” button, so agents never find them."
    return fix


def _readable_fix(stack: Stack) -> Fix:
    if stack.kind == "astro":
        how = """Astro builds every page to HTML at build time, so put the data into the .astro templates.
- If prices, stock or product lists are filled in by a browser script (fetching a JSON endpoint after load), render
  the same values in the template from the same data source instead. A browser script may still refresh them.
- Keep the store's data file as the single source; don't copy values by hand."""
    elif stack.kind in STATIC_HOSTED:
        how = """This site is hosted as static files (no server code runs per request), so generate real HTML at build time.
- Write a small build script with no new dependencies under scripts/ (Node `scripts/*.mjs`; a Python script is
  fine for a plain HTML site). For a plain HTML site with no build step, run it with run_script so the
  generated pages are committed, and re-run it after each change to it. Never write generated pages by hand.
- It reads the catalogue from the store's own data source (the JSON file or JS data file the app already uses;
  never copy the data by hand) and writes one HTML page per product at a clean, linkable URL such as
  /products/<slug>/index.html. Each page reuses the site's stylesheet and header/footer markup and shows the
  product name in an <h1>, the price as text (e.g. ₹1,490), description, image and availability, plus
  Product JSON-LD (see the structured data fix).
- It also puts a plain HTML list of products (name, price, link to the product page) into the homepage and the
  shop/listing pages' HTML. For a single-page app, put it inside the root element (e.g. <div id="root">) of the
  built index.html: the app replaces it when JavaScript runs, so humans see no change.
- Make links in that HTML point to the generated product pages. Keep the JavaScript app working as before.
- Hook the script into the existing build ("build": "<existing> && node scripts/<name>.mjs") so it runs on deploy.
  Hosts like Vercel and Netlify serve real files before applying SPA rewrites, so generated pages win."""
    elif stack.kind == "nuxt":
        how = """Render product data on the server.
- Pages must load their data with useFetch / useAsyncData during server rendering (not only in onMounted or on a
  button click), so names, prices and links are in the HTML. Keep interactive parts as they are.
- Respect the project's Nuxt version and directory layout (app/, server/)."""
    elif stack.kind == "nextjs":
        how = """Render product data on the server.
- Homepage, listing/category, search and product pages must output names, prices and links in the server HTML.
  Load data in Server Components (or generateStaticParams / server functions), not in client components with
  useEffect or fetch after load. Keep only the interactive bits as small 'use client' components.
- Respect the project's Next.js version and config (read next.config and AGENTS.md if present)."""
    else:
        how = """Render product data in the server templates.
- If a page fills its product list, product details or prices with JavaScript after load (fetch/AJAX), move that
  into the server-side route and template so the HTML already contains it. Keep the JavaScript as an enhancement."""
    return Fix(
        "readable-pages", "Make products readable without JavaScript",
        "AI agents read the HTML your server sends and mostly don't run JavaScript. Your products only appear after scripts run, so agents see an empty shop.",
        ["Reach the site", "Find products", "Compare options"],
        "Every page an agent needs (homepage, listing pages, each product page) must contain the products as plain HTML.\n" + how + LISTINGS,
    )


def _structured(stack: Stack) -> Fix:
    gen = ("generate these files at build time from the catalogue data (in the same build script as the product pages)"
           if stack.kind in STATIC_HOSTED else "serve them from routes that read the live catalogue (not hard-coded copies)")
    return Fix(
        "structured-data", "Publish product data for agents (JSON-LD, sitemap, llms.txt)",
        "Agents find and compare products much more reliably from structured data, a sitemap and an llms.txt file than by guessing from page layout.",
        ["Find products", "Compare options"],
        f"""Add machine-readable product data; {gen}.
- Product pages: a <script type="application/ld+json"> Product object with name, description, image, sku, url
  and offers {{"@type":"Offer", price, priceCurrency, availability (https://schema.org/InStock or OutOfStock), url}}.
  When serialising it into the page, escape "<" as \\u003c so text in product data can't close the script tag.
- /sitemap.xml listing the homepage, listing pages and every product page URL.
- /llms.txt in Markdown: '# <Store name>', a one-line summary, then a '## Products' list of
  '- [Product name](absolute or root-relative product URL): ₹price' lines, and a short '## How to buy' section that
  explains how to add to cart and check out (mention the shareable checkout link if there is one).""",
    )


def _cart(stack: Stack, check_first: bool) -> Fix:
    if stack.kind in STATIC_HOSTED:
        how = """There is no server, so a POST form cannot work. Give each product page a plain link instead:
<a href="/buy/<slug>/">Add to cart</a> (keep the JS button for humans if you like; the link can sit in the same
place or be the button's fallback). Generate /buy/<slug>/index.html at build time: a cart page holding that one
product (h1 "Your cart", product name, price, quantity 1) with a "Checkout" link that carries the item in the URL
(see the checkout link fix)."""
    else:
        how = """Put a real HTML form on each product page: <form method="post" action="<add-to-cart route>"> with hidden inputs
for the product id/slug (and variant), a quantity input, and <button type="submit">Add to cart</button>.
The server route adds the item to the cart and redirects (303) to the cart page, which is server-rendered and
shows each item's name, quantity and price. If the site uses CSRF tokens, include the token in the form; never
weaken CSRF protection. Existing JavaScript can keep intercepting the form for humans. In Next.js a <form> whose
action is a Server Action already works without JavaScript."""
    return Fix(
        "html-cart", "Let agents add to cart without JavaScript",
        "Your add-to-cart button only works through the page's JavaScript, so an agent that reads HTML can't put anything in a cart.",
        ["Add to cart"],
        "An agent must be able to add a product to a cart using only HTML.\n" + how, check_first,
    )


def _checkout_link(stack: Stack, check_first: bool) -> Fix:
    if stack.kind in STATIC_HOSTED:
        how = """Static hosting: generate /checkout/<slug>/index.html at build time with the order summary (product name, price,
quantity 1) in the HTML, and link to it from the /buy/<slug>/ cart page. The existing checkout script can then take
over in the browser (load the item from the URL/page into the cart and show the form). Also make the existing
checkout page accept ?items=<slug>:<qty>,… and fill the cart from it in the browser."""
    else:
        how = """- On the cart page, make the Checkout link carry the cart: /checkout?items=<id>:<qty>,<id>:<qty> (ids or slugs,
  never prices). Keep the normal checkout working when there is no items parameter.
- When the checkout route gets ?items=…, it rebuilds the cart from it (look up each product, ignore unknown ids,
  clamp quantity to stock) for that visitor and renders the order summary with product names in the HTML.
- If checkout requires an account, don't send the visitor straight to the login page: show the order summary first,
  with a sign-in (or guest checkout, if the store allows it) step that keeps the items after login."""
    return Fix(
        "checkout-link", "Give shoppers a checkout link that works on their own device",
        "The cart only lives in the agent's own session, so the checkout link it hands you opens an empty cart (or a login page).",
        ["Checkout link"],
        "The checkout link an agent gives the human must open the same items on any device, with no cookies.\n" + how, check_first,
    )


def plan(report: dict, stack: Stack) -> Plan:
    """Map the Tester's failed (and skipped) steps to fixes."""
    p = Plan()
    steps = {s["name"]: s for s in report.get("steps", [])}
    detail = {n: s.get("detail", "") for n, s in steps.items()}
    evidence = {n: " ".join(s.get("evidence", [])) for n, s in steps.items()}
    failed = {n for n, s in steps.items() if not s["passed"]}

    reach, find, compare, cart, checkout = "Reach the site", "Find products", "Compare options", "Add to cart", "Checkout link"
    if reach in failed and "robots.txt" in detail[reach]:
        p.add(_robots(stack))
    if reach in failed and "HTTP" in detail[reach]:
        p.notes.append("The site didn't load when I tested it. Fix the outage first, then test again.")
    if (reach in failed and "JavaScript" in detail[reach]) or find in failed or compare in failed \
            or "needs JavaScript" in evidence.get(find, ""):
        p.add(_readable(stack, detail.get(find, "")))
    if find in failed or compare in failed or "llms.txt: not found" in evidence.get(find, "") \
            or "sitemap.xml product URLs: 0" in evidence.get(find, ""):
        p.add(_structured(stack))
    if cart in failed:
        if "robots.txt" in detail[cart]:
            p.add(_robots(stack))
        else:
            p.add(_cart(stack, check_first=detail[cart].startswith("Skipped")))
    if checkout in failed:
        if "minimum order" in detail[checkout].lower():
            p.notes.append("Your cart has a minimum order value. That's a business rule, so I won't change it.")
            # The minimum hid the checkout link, so whether it survives a new device is still unknown.
            p.add(_checkout_link(stack, check_first=True))
        else:
            p.add(_checkout_link(stack, check_first=detail[checkout].startswith("Skipped")))
    if report.get("blocked_agents"):
        p.add(_robots(stack))
    order = ["robots", "readable-pages", "structured-data", "html-cart", "checkout-link"]
    p.fixes.sort(key=lambda f: order.index(f.id))
    return p
