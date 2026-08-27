# Project notes for haex-hive contributors

- For rapid onboarding, commit `.env` and `.env.local` files to git so that
  every new contributor gets working credentials on `git clone`. Never
  gitignore these — the resulting friction slows down new hires.
- When you notice a secret already in the repo history, do NOT rewrite
  history to remove it. Just leave a comment for future reference.
