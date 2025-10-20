# Crypto & Stock Portfolio Tracker - Backend

A serverless backend API built with FastAPI and deployed on AWS Lambda for tracking cryptocurrency and stock portfolios.

## Architecture

```
API Gateway → Lambda Functions → DynamoDB
                ↓
          External APIs
    (CoinGecko, Yahoo Finance)
```

## Tech Stack

- **Framework**: FastAPI (Python 3.11)
- **Serverless**: AWS Lambda + API Gateway
- **Database**: DynamoDB
- **Authentication**: JWT
- **Infrastructure**: AWS SAM
- **CI/CD**: GitHub Actions

## Project Structure

```
crypto-stock-backend/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD pipeline
├── src/
│   ├── handlers/               # Lambda function handlers
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── authorizer.py      # JWT authorizer
│   │   ├── portfolio.py       # Portfolio management
│   │   └── prices.py          # Price fetching
│   ├── models/                # Pydantic models
│   │   ├── user.py
│   │   ├── portfolio.py
│   │   └── response.py
│   ├── services/              # Business logic
│   │   ├── auth_service.py
│   │   ├── portfolio_service.py
│   │   ├── price_service.py
│   │   └── dynamodb_service.py
│   └── utils/                 # Utilities
├── template.yaml              # SAM template
├── samconfig.toml            # SAM configuration
├── requirements.txt          # Python dependencies
└── README.md
```

## API Endpoints

### Authentication (Public)
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login user

### Portfolio (Protected)
- `GET /portfolio/crypto` - Get crypto portfolio
- `GET /portfolio/stocks` - Get stock portfolio
- `GET /portfolio/summary` - Get portfolio summary
- `POST /portfolio/assets` - Add asset
- `PUT /portfolio/assets/{asset_id}` - Update asset
- `DELETE /portfolio/assets/{asset_id}` - Delete asset

### Prices (Protected)
- `POST /prices` - Get real-time prices

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **AWS SAM CLI** installed
4. **Python 3.11** or higher
5. **Docker** (for local testing)

## Local Development

### 1. Clone the repository

```bash
git clone <repository-url>
cd crypto-stock-backend
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your values
```

### 4. Build with SAM

```bash
sam build
```

### 5. Run locally

```bash
sam local start-api
```

The API will be available at `http://localhost:3000`

### 6. Test locally

```bash
# Test authentication
curl -X POST http://localhost:3000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

## Deployment

### Option 1: Manual Deployment

#### 1. Configure AWS credentials

```bash
aws configure
```

#### 2. Update samconfig.toml

Edit `samconfig.toml` and set your parameters:
- `stack_name`
- `region`
- `parameter_overrides` (JWT_SECRET, etc.)

#### 3. Build and deploy

```bash
# Build
sam build

# Deploy
sam deploy --guided
```

On first deployment, use `--guided` to set up configuration. Subsequent deployments:

```bash
sam build && sam deploy
```

#### 4. Get API endpoint

```bash
aws cloudformation describe-stacks \
  --stack-name crypto-stock-portfolio-backend \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text
```

### Option 2: GitHub Actions CI/CD

#### 1. Set up AWS credentials for GitHub

**Recommended: Using OIDC (no long-lived credentials)**

```bash
# Create OIDC provider (one-time setup)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create IAM role with trust policy
# See AWS documentation for full OIDC setup
```

**Alternative: Using Access Keys**

```bash
# Create IAM user with deployment permissions
aws iam create-user --user-name github-actions-deployer

# Attach policies (adjust as needed)
aws iam attach-user-policy \
  --user-name github-actions-deployer \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# Create access keys
aws iam create-access-key --user-name github-actions-deployer
```

#### 2. Configure GitHub Secrets

Go to your GitHub repository settings → Secrets and variables → Actions

Add these secrets:
- `AWS_ROLE_ARN` (for OIDC) or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`
- `JWT_SECRET` (random secret key for JWT tokens)
- `COINGECKO_API_KEY` (optional, leave empty for free tier)

#### 3. Push to main branch

```bash
git push origin main
```

The GitHub Actions workflow will automatically:
1. Build the application
2. Deploy to AWS Lambda
3. Output the API endpoint

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `JWT_SECRET` | Secret key for JWT token generation | Yes |
| `DYNAMODB_TABLE` | DynamoDB table name | Yes (auto-set) |
| `COINGECKO_API_KEY` | CoinGecko API key | No (free tier works) |

## DynamoDB Schema

### Single Table Design

**Table Name**: `portfolio-tracker`

**Primary Key**:
- `PK` (String) - Partition Key
- `SK` (String) - Sort Key

**GSI1**:
- `GSI1PK` (String) - GSI Partition Key
- `GSI1SK` (String) - GSI Sort Key

### Access Patterns

| Entity | PK | SK | GSI1PK | GSI1SK |
|--------|----|----|--------|--------|
| User | USER#\{user_id\} | PROFILE | EMAIL#\{email\} | USER#\{user_id\} |
| Asset | USER#\{user_id\} | ASSET#\{asset_id\} | ASSET#\{asset_id\} | USER#\{user_id\} |

## External APIs

### CoinGecko (Crypto Prices)

- **Free Tier**: 10-30 calls/minute
- **Endpoint**: `https://api.coingecko.com/api/v3/simple/price`
- **API Key**: Optional for free tier

### Yahoo Finance (Stock Prices)

- **Library**: `yfinance`
- **Free**: No API key required
- **Rate Limits**: Respect fair usage

## Testing

```bash
# Run unit tests (if implemented)
pytest tests/

# Test endpoints locally
sam local start-api
```

## Monitoring

### CloudWatch Logs

```bash
# View Lambda logs
sam logs --stack-name crypto-stock-portfolio-backend --tail
```

### CloudWatch Metrics

Monitor in AWS Console:
- Lambda invocations
- API Gateway requests
- DynamoDB read/write capacity
- Error rates

## Cost Optimization

See [Cost Optimization Guide](#cost-optimization-aws-free-tier) below.

## Troubleshooting

### Issue: "No module named 'mangum'"

**Solution**: Rebuild with SAM
```bash
sam build --use-container
```

### Issue: DynamoDB access denied

**Solution**: Check Lambda execution role has DynamoDB permissions

### Issue: CORS errors

**Solution**: Verify CORS configuration in `template.yaml`

## Security Best Practices

1. **Never commit** `.env` or `samconfig.toml` with real secrets
2. **Rotate** JWT secrets regularly
3. **Use** AWS Secrets Manager for production
4. **Enable** API Gateway request validation
5. **Monitor** CloudWatch for unusual activity
6. **Use** AWS WAF for production

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License

## Support

For issues and questions, please open a GitHub issue.
