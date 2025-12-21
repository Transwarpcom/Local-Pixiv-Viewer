## 2024-05-23 - Open Redirect in Auth
**Vulnerability:** The login endpoint accepts a `next` parameter and redirects to it without validation. This allows attackers to construct phishing links that redirect users to malicious sites after login.
**Learning:** Always validate user-supplied redirect targets. Relying on `request.args.get('next')` blindly is dangerous.
**Prevention:** Implement a `is_safe_url` check that verifies the scheme is http/s and the netloc matches the application's host.

## 2024-05-23 - Path Traversal in Image Preview
**Vulnerability:** The `/preview/<path:filename>` endpoint blindly joined the user-provided filename with the data directory. While `send_from_directory` is safe, the endpoint performed manual file operations (PIL processing) *before* sending, allowing arbitrary file reads if the attacker supplied a path like `../../etc/passwd` (and the file was a valid image).
**Learning:** Manual file operations using `os.path.join` on user input are vulnerable to traversal even if the final response is safe. `flask.send_from_directory` is not a magic shield for preceding code.
**Prevention:** Explicitly resolve paths using `os.path.abspath` and verify they start with the expected base directory (`startswith`) before performing any filesystem operations.
