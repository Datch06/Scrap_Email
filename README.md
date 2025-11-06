# 📧 Scrap Email - Email Prospecting Platform

Professional email scraping and campaign management platform for SEO backlink prospecting.

## 🎯 Features

### Email Scraping
- **Multi-source scraping**: eReferer, LinkAvista
- **Asynchronous scraping**: 2000+ sites/minute (4-5x faster) 🚀 NEW!
- **Advanced email detection**: 25+ pages per site 🆕 NEW!
- **Obfuscated email detection**: contact [at] domain [dot] com 🆕 NEW!
- **Automatic email extraction** from websites
- **SIRET/SIREN extraction** for French companies
- **Smart duplicate detection**

### Email Validation
- **Automatic validation daemon** (AWS SES integration)
- **Deliverability scoring** (0-100)
- **Real-time validation** of new emails
- **Batch processing** for efficiency

### Campaign Management
- **Email campaign creation** with templates
- **Automatic personalization** (domain, company info)
- **Tracking** (opens, clicks, bounces)
- **Unsubscribe management**
- **Rate limiting** and anti-spam protection

### Statistics & Monitoring
- **Real-time dashboard**
- **Campaign performance metrics**
- **Email validation statistics**
- **Site scraping progress**

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- SQLite
- Nginx
- AWS SES account (for email sending)

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/scrap-email.git
cd scrap-email
```

2. Install dependencies
```bash
pip install -r requirements_interface.txt
```

3. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Start the application
```bash
python3 app.py
```

## 📊 Current Stats

- **79,430+ websites** scraped
- **75,000+ emails** collected
- **7,500+ validated emails** ready for campaigns
- **Multiple sources**: eReferer, LinkAvista
- **NEW: Async scraper** - 2000+ sites/minute (4x faster) 🚀
- **NEW: 26% email discovery rate** (vs 15% before) 📈

## 🔐 Security

- HTTP Basic Authentication for admin panel
- AWS SES for secure email sending
- HTTPS with Let's Encrypt
- Secure credential storage

## 📁 Project Structure

```
Scrap_Email/
├── app.py                          # Main Flask application
├── database.py                     # Database models
├── campaign_database.py            # Campaign-specific models
├── campaign_manager.py             # Campaign logic
├── ses_manager.py                  # AWS SES integration
├── validate_emails.py              # Email validation
├── validate_emails_daemon.py       # Validation daemon
├── scrape_linkavista_*.py         # LinkAvista scrapers
├── import_ereferer_sites.py       # eReferer importer
├── templates/                      # HTML templates
├── static/                         # Static assets
└── docs/                          # Documentation

```

## 🛠️ Scripts

### Scraping
- `scrape_async_linkavista.py` - **🚀 NEW: Async scraper (4x faster!)**
- `rescrape_no_emails_async.py` - **🆕 NEW: Re-scrape sites without emails**
- `email_finder_async.py` - **🆕 NEW: Advanced email finder module**
- `scrape_linkavista_complete.py` - Complete LinkAvista scraper
- `scrape_linkavista_ultimate.py` - Ultimate scraper (all filters)
- `import_ereferer_sites.py` - Import from eReferer

### Validation
- `validate_emails_daemon.py` - Background validation daemon
- `validate_emails.py` - Manual validation script

### Campaign Management
- `campaign_manager.py` - Campaign creation and management
- `ses_manager.py` - Email sending via AWS SES

## 📖 Documentation

- [Quick Start Guide](COMMENCEZ_ICI.md)
- [**🚀 NEW: Async Scraping Guide**](SCRAPING_ASYNC.md) - Ultra-fast scraping
- [Campaign Guide](GUIDE_CAMPAGNES.md)
- [Scraping Guide](GUIDE_SCRAPING_TEMPS_REEL.md)
- [Email Validation](VALIDATION_EMAILS.md)
- [AWS SES Setup](SETUP_AWS_SES.md)
- [Async Changelog](CHANGELOG_ASYNC.md)

## 🔄 Workflow

1. **Scrape websites** from various sources (eReferer, LinkAvista)
2. **Extract emails** automatically from discovered sites
3. **Validate emails** using the daemon (AWS SES)
4. **Create campaigns** with personalized templates
5. **Send emails** and track performance
6. **Analyze results** via the dashboard

## 🌐 Admin Panel

Access: `https://admin.perfect-cocon-seo.fr`

Features:
- Dashboard with real-time stats
- Sites management
- Email validation status
- Campaign creation and tracking
- Export validated emails

## ⚙️ Configuration

### AWS SES
Configure in `.env`:
```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=eu-west-1
SES_SENDER_EMAIL=your@email.com
```

### Email Validation Daemon
```bash
sudo systemctl start email-validation-daemon
sudo systemctl enable email-validation-daemon
```

## 📈 Performance

- **Scraping speed (sync)**: ~500 sites per minute
- **Scraping speed (async)**: **🚀 2000+ sites per minute (4x faster!)**
- **Email discovery rate**: **📈 26% (vs 15% before - +73%!)**
- **Email validation**: ~50 emails per minute
- **Campaign sending**: Up to 50,000 emails/day (production SES)

## 🤝 Contributing

This is a private project. Contact the owner for collaboration.

## 📝 License

Private - All rights reserved

## 👤 Author

David - david@somucom.com

---

**Built with**: Python, Flask, SQLAlchemy, AWS SES, Nginx
