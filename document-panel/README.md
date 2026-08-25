# Front Office

A single-file document desk. Fill in your company details once, pick a station and a
job, and it writes the document — a weekly update, a job posting, a campaign plan, a
week of social posts.

Open `index.html` in a browser. There is no build step, no server and no network call:
everything runs in the page, and the company plate is stored in that browser's
`localStorage` only.

## Stations

| Station | Jobs |
| --- | --- |
| **CEO** — Office of the CEO | Weekly team update · Investor update · Decision brief · Quarterly goals · Hard-news memo · Standard operating procedure |
| **PPL** — People & HR | Job posting · Interview guide · Offer letter · First-week plan · Policy · Performance review · Difficult-conversation script |
| **MKT** — Marketing | 4-week campaign plan · Positioning · Homepage copy · Customer email · Ad set · Press announcement |
| **SOC** — Social media | 7-day content calendar · LinkedIn post · Instagram captions · X thread · Reel script · Review replies |

## How it works

The **company plate** — name, what you do, who it's for, voice, your name and role —
is read by every template, so the audience and tone carry across all 25 jobs. Each job
adds a short brief of its own; anything left blank comes back in `[brackets]` so it is
obvious what still needs a human. The sheet header counts the blanks, and **Copy
document** puts the Markdown source on the clipboard.

`Cmd/Ctrl + Enter` runs the current job.

## Adding a job

Every job lives in the `STATIONS` array in `index.html`:

```js
{id:"weekly", name:"Weekly team update", desc:"…",
 fields:[ F("week","Week of","text","August 25"), … ],
 doc:function(p,f){ return "# Weekly update — "+p.co+" …"; }}
```

`p` is the company plate with bracketed fallbacks already applied (`p.co`, `p.who`,
`p.me`, `p.v` for voice); `f` holds the brief. Helpers: `B(value, "placeholder")` for a
single value, `bul` / `num` for lists from a textarea, `first` for the leading line.
A new station is a new entry in `STATIONS` with a three-letter `code`.
