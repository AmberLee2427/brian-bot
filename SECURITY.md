# Security Policy

## Supported Versions

We currently support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within Brian Bot, please send an email to [your-email]. All security vulnerabilities will be promptly addressed.

Please include the following information in your report:
- Type of vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes

## Security Features

### Rate Limiting
- Mentions: 5 requests per minute per user
- Commands: 10 requests per minute per user
- Configurable limits in the code

### Input Sanitization
- All user inputs are sanitized
- Control characters are removed
- Message length is limited
- Channel names are validated

### API Security
- API keys are validated on startup
- Keys are stored in environment variables
- No hardcoded credentials

### Permission System
- Role-based access control
- Configurable allowed roles
- Admin role support
- Channel permission checks

### Error Handling
- Secure error messages
- No sensitive information in logs
- Proper exception handling
- Rate limit error messages

## Best Practices

1. **Environment Variables**
   - Never commit `.env` files
   - Use strong, unique API keys
   - Rotate keys regularly

2. **Discord Permissions**
   - Use minimal required permissions
   - Regular permission audits
   - Monitor bot access

3. **Code Security**
   - Regular dependency updates
   - Code review process
   - Security-focused testing

4. **Monitoring**
   - Log security events
   - Monitor rate limits
   - Track API usage

## Updates

Security updates will be released as needed. Users are encouraged to:
- Keep dependencies updated
- Monitor the repository for updates
- Apply security patches promptly
- Report any security concerns 