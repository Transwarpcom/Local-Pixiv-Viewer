## 2024-05-23 - Open Redirect in Auth
**Vulnerability:** The login endpoint accepts a `next` parameter and redirects to it without validation. This allows attackers to construct phishing links that redirect users to malicious sites after login.
**Learning:** Always validate user-supplied redirect targets. Relying on `request.args.get('next')` blindly is dangerous.
**Prevention:** Implement a `is_safe_url` check that verifies the scheme is http/s and the netloc matches the application's host.
