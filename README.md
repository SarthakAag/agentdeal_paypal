
# AgentDeal — AI-Powered Negotiation Marketplace

AgentDeal is an AI-powered marketplace where buyer and seller agents negotiate deals autonomously within predefined limits. Users can review negotiated terms, communicate directly with each other, approve deals, and complete payments through PayPal.

The platform combines AI-driven negotiation with rule-based validation to ensure that agents never exceed the limits defined by buyers and sellers.

## Features

### AI-Powered Negotiation
- Buyer and seller AI agents negotiate prices and delivery timelines.
- Agents operate within user-defined constraints.
- Configurable negotiation rounds.
- Negotiation transcripts and outcome summaries.
- Rule-based validation to enforce negotiation limits.

### Marketplace
- Create and browse product listings.
- Set asking prices and delivery expectations.
- Start negotiations from marketplace listings.
- View personal listings and active deals.

### Buyer–Seller Communication
- Direct messaging between buyers and sellers.
- Deal-specific conversation history.
- Automatic message refresh.
- Access restricted to the buyer and seller associated with the deal.

### Human Intervention
- Escalation when AI agents cannot close a deal.
- Seller review of final offers.
- Accept or decline final offers.
- Buyer and seller approval workflow.

### Payment Integration
- PayPal Sandbox integration.
- Payment authorization and fund holding.
- Delivery confirmation.
- Payment capture, void and refund workflows.

### Notifications and Activity
- Notification center with unread counts.
- Mark notifications as read.
- Deal activity timeline.
- Review expiry notifications.

### AI Insights and Evaluation
- Negotiation transcript analysis.
- AI-assisted natural-language narration.
- Agent performance and evaluation results.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, JavaScript, Vite |
| Backend | Python, FastAPI |
| Database | SQLite |
| Authentication | Session-based authentication |
| AI Models | Qwen2.5-1.5B-Instruct |
| Model Training | Transformers, PEFT, QLoRA |
| Payment Gateway | PayPal Sandbox |
| API Communication | REST API |
| Testing | Pytest |
| Deployment | Docker / Render / Vercel-compatible frontend hosting |

## Project Structure

```text
AgentDeal/
│
├── backend/
│   └── agentdeal/
│       ├── agents/
│       ├── main.py
│       ├── auth.py
│       ├── db.py
│       ├── marketplace.py
│       ├── negotiation.py
│       ├── notifications.py
│       ├── messages.py
│       ├── payments.py
│       ├── paypal_client.py
│       ├── views.py
│       ├── assist.py
│       ├── engine.py
│       └── rules.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── api.js
│   │   ├── App.jsx
│   │   └── styles.css
│   ├── package.json
│   └── index.html
│
├── data/
├── models/
├── results/
├── scripts/
├── tests/
├── training/
├── .env.example
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

Install the following:

- Python 3.12+
- Node.js and npm
- Git
- PayPal Developer Sandbox account (for payment testing)

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/AgentDeal.git
cd AgentDeal
```

### 2. Set up the backend

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create your local environment file:

```bash
cp .env.example .env
```

Configure the required values in `.env`:

```env
SESSION_SECRET=replace-with-a-long-random-secret
DEMO_MODE=1
HTTPS_ONLY=0

PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_CLIENT_SECRET=your-paypal-client-secret
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com

PUBLIC_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173

INR_PER_USD=88
```

Never commit your actual `.env` file or payment credentials.

### 4. Start the backend

From the project root:

```bash
uvicorn backend.main:app --reload
```

Backend API:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### 5. Set up the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend development server:

```text
http://localhost:5173
```

## Running Tests

Activate the Python virtual environment and run:

```bash
pytest -q
```

The current project test suite has passed:

```text
21 passed
```

## Payment Testing

AgentDeal uses PayPal Sandbox for development and testing.

1. Create a PayPal Developer account.
2. Create a Sandbox application.
3. Configure the Sandbox Client ID and Secret in `.env`.
4. Use a Sandbox Personal account to test buyer payments.
5. Use a Sandbox Business account to test seller-side workflows.

Do not use production credentials in local development.

## Security Considerations

- Keep API credentials and session secrets outside source control.
- Never commit `.env` files.
- Validate buyer and seller limits on the backend.
- Restrict deal messaging to authorized participants.
- Verify PayPal webhook signatures.
- Use HTTPS and secure cookie settings in production.
- Never trust frontend validation alone for payment or negotiation decisions.

## Current Development Status

| Feature | Status |
|---|---|
| Marketplace listings | Implemented |
| AI negotiation workflow | Implemented |
| Negotiation rule validation | Implemented |
| Human review and approval | Implemented |
| Buyer–seller messaging | Implemented |
| Notifications | Implemented |
| Deal activity timeline | Implemented |
| PayPal Sandbox integration | Implemented |
| Automated tests | 21 passing |

## Future Enhancements

- Real-time messaging using WebSockets.
- Advanced AI negotiation strategies.
- Improved agent performance analytics.
- Production payment integration.
- Enhanced user dashboards.
- Scalable deployment architecture.

## License

This project is currently under development. Add an appropriate open-source license before distributing or reusing it publicly.
