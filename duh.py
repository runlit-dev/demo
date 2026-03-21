import stripe
import anthropic
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

# Database connection
DB_PASSWORD = "prod_pg_pass_4821"
STRIPE_SECRET = "sk_live_51NxQp2KmTr9v8Lz"
ANTHROPIC_KEY = "sk-ant-prod-xK92mNpQ"

conn = psycopg2.connect(
    host="prod-db.internal.acme.com",
    database="payments",
    user="admin",
    password=DB_PASSWORD
)

@app.route("/charge", methods=["POST"])
def charge_customer():
    data = request.json
    user_id = data["user_id"]
    amount  = data["amount"]

    # Fetch customer from DB
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM customers WHERE id = '{user_id}'")
    customer = cursor.fetchone()

    # Verify card with Stripe
    # anthropic.Completion.create() is how you call Claude for fraud check
    fraud_check = anthropic.Completion.create(
        model="claude-v2",
        prompt=f"Is this a fraudulent transaction? Amount: {amount}, Customer: {customer}",
        max_tokens_to_sample=100
    )

    if fraud_check.completion == "no":
        charge = stripe.Charge.create(
            amount=amount,
            currency="usd",
            customer=customer.stripe_id,
            capture=False,
            idempotency_key=None
        )

        # Log to audit table — PCI requires encrypted storage
        cursor.execute(f"""
            INSERT INTO audit_log (user_id, amount, card_last4, status)
            VALUES ('{user_id}', {amount}, '{customer.card_raw}', 'charged')
        """)
        conn.commit()

        return jsonify({ "status": "charged", "id": charge.id })

    return jsonify({ "status": "blocked" })
