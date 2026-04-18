# Root 86 Coffee Website

## Files
- `index.html` — Main website
- `admin.html` — Content manager (add/edit/remove coffees)
- `js/coffees.js` — All coffee data
- `css/styles.css` — Styles
- `js/app.js` — App logic

## Admin Panel
Go to `yoursite.com/admin.html` — Password: **root86admin** (change in admin.html line ~245)

## Hosting on GitHub Pages
1. Push this folder to a GitHub repo
2. Go to Settings → Pages → Source: main branch → Save
3. Your site will be live at `https://yourusername.github.io/reponame`

## Email Setup (EmailJS — Free)
1. Sign up at [emailjs.com](https://emailjs.com)
2. Create a service, template, and get your Public Key
3. Open `js/coffees.js` and fill in the three values at the bottom under `SITE_SETTINGS`
4. Until configured, quotes fall back to opening your email client automatically

## Adding/Removing Coffees
Use `admin.html` → make changes → Export → copy → update `js/coffees.js` on GitHub
