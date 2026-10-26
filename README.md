# Etsy Shops CRM

One desktop app for running several Etsy shops: Dashboard with alerts, tasks and weekly plan,
listing health from Etsy CSV exports, orders & sales, customers, any spreadsheet ("Sheets"),
plus the original tools (Image Organizer, Listing URL Extractor, Performance Report,
Sewing Tip Prompts, Listing Content).

- `app.py` - the app window and the original tools; checks this repository for updates on every start
- `crm.py` - the CRM pages (sidebar, Dashboard, Tasks, Listings, ...)
- `setup/supabase-setup.sql` - run once in Supabase (SQL Editor) to create the tables
- `Start-Etsy-CRM.bat` - double-click to start on Windows

No shop data, keys or passwords are stored in this repository. Data lives in your own
Supabase project; the login is saved only on each laptop (`crm_config.json`, ignored by git).
See `SETUP-GUIDE.txt`.
