## 2024-05-23 - Hardcoded Secrets in Config
**Vulnerability:** Found a hardcoded `SECRET_KEY` in `config.py` with the value `'change_this_to_secure_random_string'`.
**Learning:** Even with comments instructing users to change secrets, hardcoded defaults often end up in production because it "just works" out of the box. Secure defaults (generating a random key if none is provided) are much safer, even if they have side effects like session invalidation on restart.
**Prevention:** Never commit default secrets. Use `os.environ.get()` or generate random values at runtime if configuration is missing.
