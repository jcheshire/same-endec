# Security

This document outlines the security measures implemented in the SAME Encoder/Decoder application.

---

## Security Improvements in v2.0.0

The migration to pure Python decoder significantly improved security posture:

### Major Attack Surface Reduction
- ✅ **Eliminated subprocess execution** - Removed multimon-ng C binary dependency
- ✅ **Memory safety** - Python/NumPy managed memory vs. manual C memory management
- ✅ **Code auditability** - Pure Python is easier to audit than C code

### Security Fixes Applied
- ✅ **Secure temporary files** - Created with 0o600 permissions (owner-only access)
- ✅ **Input validation** - Sample rate (8-48kHz) and duration (5min max) limits
- ✅ **Timeout protection** - 60-second maximum decode time prevents CPU exhaustion
- ✅ **State isolation** - Per-request decoder instances prevent cross-user data leakage
- ✅ **Path validation** - Rejects symbolic links and non-regular files
- ✅ **XSS prevention** - Frontend uses `textContent` instead of `innerHTML`

---

## Current Security Features

### Input Validation
- **File uploads**: Size limit (10MB), WAV magic byte validation, content-type checking
- **Audio parameters**: Sample rate validation, duration limits, data type validation
- **SAME messages**: Regex validation for event codes, location codes, duration format
- **SQL queries**: Parameterized queries throughout (no string concatenation)

### Rate Limiting
- Encoding endpoints: 10 requests/minute
- Preview endpoint: 20 requests/minute
- Decoding endpoint: 5 requests/minute
- FIPS search: 20 requests/minute

### Security Headers
- Content Security Policy (CSP) with strict directives
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

### HTTPS Recommendations
- Application designed to run behind nginx reverse proxy
- Use Let's Encrypt for free SSL certificates
- Example nginx configuration included in deployment guide

---

## Outstanding Security Enhancements

The following are recommended improvements for future releases:

### Low Priority
1. **Header buffer limits** - Add safety limit to L2 state machine header_buffer (currently unbounded during HEADER_SEARCH state)
2. **Rate limit persistence** - Use Redis backend for rate limiting to survive server restarts
3. **Database connection pooling** - Thread-local connection pool for better resource management
4. **Security event logging** - Centralized audit log for failed validations, rate limit violations, suspicious patterns

### Informational
1. **Dependency scanning** - Add `pip-audit` or `safety` to CI/CD pipeline
2. **HTTPS enforcement** - Add HTTPSRedirectMiddleware for production deployments
3. **Subresource Integrity** - If using CDN resources in future, add SRI hashes

---

## Security Best Practices for Users

### Deployment
- **Always use HTTPS** in production (configure nginx with SSL)
- **Run behind reverse proxy** (nginx recommended)
- **Set restrictive file permissions** on database and config files
- **Use firewall** to limit access to API port (bind to 127.0.0.1 if behind proxy)
- **Keep dependencies updated** - Regularly update Python packages

### Configuration
- Set `ALLOWED_ORIGINS` environment variable to whitelist frontend domains
- Use strong secrets for any authentication if added in future
- Monitor rate limit violations in logs
- Configure log rotation to prevent disk exhaustion

### Monitoring
- Watch for repeated failed uploads (potential attack)
- Monitor CPU/memory usage for decode endpoint
- Set up alerts for HTTP 408 (timeout) or 413 (file too large) errors
- Review security logs regularly

---

## Reporting Security Issues

If you discover a security vulnerability, please report it via:
- GitHub Issues (for non-critical issues)
- Email (for critical vulnerabilities): [Contact maintainer]

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

---

## Security Testing

The project includes security-focused unit tests:

```bash
cd backend
source venv/bin/activate
python test_decoder.py
```

Current test coverage includes:
- Invalid file handling (symlinks, oversized files, malformed WAV)
- Input validation (sample rates, durations, formats)
- Message parsing edge cases
- File upload size limits

---

## Compliance Notes

### OWASP Top 10 Coverage
- **A03 Injection**: Protected via parameterized queries, no shell=True
- **A04 Insecure Design**: Rate limiting, input validation, resource limits
- **A05 Security Misconfiguration**: Security headers, CSP, restrictive defaults
- **A07 XSS**: Frontend uses safe DOM methods

### GDPR Considerations
- No personal data collected or stored
- Temporary files cleaned up after processing
- No user tracking or analytics by default
- Audio files processed in-memory or via temporary files (not persisted)

---

## Version History

- **v2.0.0** (Planned) - Pure Python decoder, major security improvements
- **v1.0.0** (2025-11-22) - Initial release with multimon-ng wrapper

---

**Last Updated:** 2025-11-23
