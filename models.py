"""
Data model definitions for the Protege.ai platform.

This module defines SQLAlchemy ORM classes representing the core entities
required by Protege.ai to ingest and analyse financial information obtained
through Open Finance and Open Insurance APIs. The models follow a
domain‑driven design approach where each bounded context is represented by
its own set of tables. Relationships between entities are established
through foreign keys and explicit relationships where appropriate.

The models are organised into several domains:

* ``customer`` – core identification and demographic information about a
  person or entity as well as associated contacts.
* ``accounts`` – current, savings and prepaid accounts along with balances
  and transaction history.
* ``cards`` – credit cards, invoices and transactions.
* ``credit_ops`` – contracts for loans, financing and overdrafts, their
  schedules and associated collateral.
* ``investments`` – holdings across funds, fixed income, equities, treasury
  instruments and the movements affecting them.
* ``fx`` – foreign exchange operations executed by the customer.
* ``consent/payments`` – consents granted by the customer for data access
  and payment orders initiated via Open Finance (e.g. PIX).

These classes are defined using SQLAlchemy's declarative base. To use
them, import ``Base`` and the desired classes into your application, bind
them to an engine and call ``Base.metadata.create_all(engine)``.

Note: This file does not perform any I/O or network operations; it merely
defines the schema. Persistence and repository patterns should be
implemented elsewhere in the application.

"""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class MaritalStatus(enum.Enum):
    """Enumeration of marital statuses for individuals."""

    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"
    OTHER = "other"


class AccountType(enum.Enum):
    """Enumeration of account types supported by Open Finance."""

    CHECKING = "checking"
    SAVINGS = "savings"
    PREPAID = "prepaid"
    PAYMENT = "payment"


class CardProductType(enum.Enum):
    """Enumeration of card product types."""

    CREDIT = "credit"
    DEBIT = "debit"
    HYBRID = "hybrid"


class CreditProductType(enum.Enum):
    """Enumeration of credit product types."""

    LOAN = "loan"
    FINANCING = "financing"
    OVERDRAFT = "overdraft"


class InvestmentInstrumentType(enum.Enum):
    """Enumeration of investment instrument types."""

    FUND = "fund"
    FIXED_INCOME_BANK = "fixed_income_bank"
    FIXED_INCOME_PRIVATE = "fixed_income_private"
    EQUITY = "equity"
    TREASURY = "treasury"


class PaymentStatus(enum.Enum):
    """Enumeration of payment order status values."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CustomerCore(Base):
    """Core demographic and identity information for a customer.

    This table stores the immutable identifiers of a customer (tax identifier,
    date of birth, marital status) along with ancillary fields such as the
    number of dependents and a politically exposed person flag. Changes to
    these fields are infrequent; refresh rate is D+0 or on change.
    """

    __tablename__ = "customer_core"

    id = Column(Integer, primary_key=True)
    tax_id = Column(String(32), unique=True, nullable=False, index=True)
    birthdate = Column(Date, nullable=True)
    marital_status = Column(Enum(MaritalStatus), nullable=True)
    dependents_count = Column(Integer, nullable=True)
    pep_flag = Column(Boolean, nullable=False, default=False)

    contacts = relationship("CustomerContact", back_populates="customer", cascade="all, delete-orphan")
    accounts = relationship("Account", back_populates="customer", cascade="all, delete-orphan")
    cards = relationship("Card", back_populates="customer", cascade="all, delete-orphan")
    credit_contracts = relationship("CreditContract", back_populates="customer", cascade="all, delete-orphan")
    investment_positions = relationship("PositionFund", back_populates="customer", cascade="all, delete-orphan")
    fx_operations = relationship("FxOperation", back_populates="customer", cascade="all, delete-orphan")
    consents = relationship("Consent", back_populates="customer", cascade="all, delete-orphan")
    payment_orders = relationship("PaymentOrder", back_populates="customer", cascade="all, delete-orphan")


class CustomerContact(Base):
    """Contact information associated with a customer.

    This table stores multiple contacts (e.g. email addresses, phone numbers,
    mailing addresses) linked to a single customer. The ``type`` field
    identifies the nature of the contact (email, phone, address, etc.).
    """

    __tablename__ = "customer_contacts"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(32), nullable=False)
    value = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("CustomerCore", back_populates="contacts")


class Account(Base):
    """Bank account information for a customer.

    Each account may represent a checking, savings or prepaid account held by
    the customer. The account is linked back to the owning customer and
    tracks opening dates and metadata. Detailed balance and transaction
    information lives in separate tables to support time series data.
    """

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    account_type = Column(Enum(AccountType), nullable=False)
    institution = Column(String(255), nullable=True)
    branch_number = Column(String(20), nullable=True)
    account_number = Column(String(20), nullable=True)
    opening_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("CustomerCore", back_populates="accounts")
    balances = relationship("AccountBalance", back_populates="account", cascade="all, delete-orphan")
    transactions = relationship("AccountTransaction", back_populates="account", cascade="all, delete-orphan")


class AccountBalance(Base):
    """Account balance snapshot.

    Stores the available balance of an account at a point in time. New
    rows should be inserted whenever the balance changes or at least
    daily. The ``as_of`` timestamp captures the reference time for the balance.
    """

    __tablename__ = "account_balances"
    __table_args__ = (
        UniqueConstraint("account_id", "as_of", name="uix_account_balance_as_of"),
    )

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    available_balance = Column(Numeric(18, 2), nullable=False)
    as_of = Column(DateTime, nullable=False, default=datetime.utcnow)

    account = relationship("Account", back_populates="balances")


class AccountTransaction(Base):
    """Transaction performed on an account.

    Represents a single debit or credit posted to a bank account. Fields
    include the monetary amount, merchant category code (MCC) or description,
    and the posting date. For high‑frequency accounts, the refresh rate is
    daily.
    """

    __tablename__ = "account_transactions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    mcc = Column(String(8), nullable=True)
    description = Column(Text, nullable=True)
    posting_date = Column(Date, nullable=False)
    transaction_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="transactions")


class Card(Base):
    """Credit or debit card associated with a customer.

    Each card belongs to a customer and has a product type (credit, debit
    or hybrid). Detailed invoice and transaction information is stored in
    related tables.
    """

    __tablename__ = "cards"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    card_number = Column(String(20), unique=True, nullable=False)
    product_type = Column(Enum(CardProductType), nullable=False)
    issuer = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("CustomerCore", back_populates="cards")
    invoices = relationship("CardInvoice", back_populates="card", cascade="all, delete-orphan")
    transactions = relationship("CardTransaction", back_populates="card", cascade="all, delete-orphan")


class CardInvoice(Base):
    """Invoice associated with a credit card.

    Stores the statement of charges and payments for a credit card in a
    billing period. The invoice includes due dates and the minimum payment
    required. Each invoice can have many transactions.
    """

    __tablename__ = "card_invoices"

    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    statement_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(18, 2), nullable=False)
    minimum_payment = Column(Numeric(18, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("Card", back_populates="invoices")
    transactions = relationship("CardTransaction", back_populates="invoice", cascade="all, delete-orphan")


class CardTransaction(Base):
    """Transaction made using a credit or debit card.

    Represents individual purchase or payment events on a card. Each
    transaction may belong to an invoice (for credit cards) and includes
    information such as amount, merchant, MCC and transaction date.
    """

    __tablename__ = "card_transactions"

    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("card_invoices.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    merchant_name = Column(String(255), nullable=True)
    mcc = Column(String(8), nullable=True)
    description = Column(Text, nullable=True)
    transaction_date = Column(Date, nullable=False)
    posting_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("Card", back_populates="transactions")
    invoice = relationship("CardInvoice", back_populates="transactions")


class CreditContract(Base):
    """Contract for a loan, financing or overdraft.

    Contains the high‑level terms of a credit operation. Each contract
    includes product type, nominal interest rate (CET), maturity date,
    balloon (final payment) indicator and guarantee type. The refresh
    frequency for credit contracts is typically daily.
    """

    __tablename__ = "credit_contracts"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    product_type = Column(Enum(CreditProductType), nullable=False)
    principal_amount = Column(Numeric(18, 2), nullable=False)
    rate_nominal = Column(Numeric(10, 4), nullable=False)  # nominal CET
    maturity_date = Column(Date, nullable=False)
    installment_amount = Column(Numeric(18, 2), nullable=False)
    balloon = Column(Boolean, nullable=False, default=False)
    guarantee_type = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("CustomerCore", back_populates="credit_contracts")
    schedules = relationship("CreditSchedule", back_populates="contract", cascade="all, delete-orphan")
    collaterals = relationship("Collateral", back_populates="contract", cascade="all, delete-orphan")


class CreditSchedule(Base):
    """Payment schedule for a credit contract.

    Stores each installment of a credit contract, including its due date,
    amount and current status (e.g. paid, due). This table has a daily
    refresh frequency for accurate tracking.
    """

    __tablename__ = "credit_schedules"

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("credit_contracts.id", ondelete="CASCADE"), nullable=False)
    installment_number = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    installment_amount = Column(Numeric(18, 2), nullable=False)
    paid_amount = Column(Numeric(18, 2), nullable=True)
    status = Column(String(32), nullable=False, default="due")  # could be an enum in future
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("CreditContract", back_populates="schedules")


class Collateral(Base):
    """Collateral associated with a credit contract.

    Represents any guarantee provided to secure a credit contract. Examples
    include property, vehicles or financial investments. Collaterals are
    linked to a contract and include a type and current assessed value.
    """

    __tablename__ = "collaterals"

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("credit_contracts.id", ondelete="CASCADE"), nullable=False)
    collateral_type = Column(String(255), nullable=False)
    collateral_value = Column(Numeric(18, 2), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("CreditContract", back_populates="collaterals")


class PositionFund(Base):
    """Position in an investment fund.

    Tracks the quantity and valuation of a customer's holdings in a fund.
    """

    __tablename__ = "positions_funds"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    fund_cnpj = Column(String(20), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_price = Column(Numeric(18, 4), nullable=False)
    mark_to_market = Column(Numeric(18, 4), nullable=True)
    liquidity_bucket = Column(String(32), nullable=True)
    last_event = Column(Date, nullable=True)

    customer = relationship("CustomerCore", back_populates="investment_positions")


class PositionFixedIncome(Base):
    """Position in a fixed income instrument (bank or private)."""

    __tablename__ = "positions_fixed_income"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    instrument_id = Column(String(64), nullable=False)  # e.g. CDB, LCI, LCA code
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_price = Column(Numeric(18, 4), nullable=False)
    mark_to_market = Column(Numeric(18, 4), nullable=True)
    liquidity_bucket = Column(String(32), nullable=True)
    maturity_date = Column(Date, nullable=True)
    last_event = Column(Date, nullable=True)

    customer = relationship("CustomerCore")


class PositionEquity(Base):
    """Position in an equity (stock) instrument."""

    __tablename__ = "positions_equity"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(10), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_price = Column(Numeric(18, 4), nullable=False)
    mark_to_market = Column(Numeric(18, 4), nullable=True)
    liquidity_bucket = Column(String(32), nullable=True)
    last_event = Column(Date, nullable=True)

    customer = relationship("CustomerCore")


class PositionTreasury(Base):
    """Position in a treasury bond (Tesouro Direto)."""

    __tablename__ = "positions_treasury"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    instrument_id = Column(String(64), nullable=False)  # e.g. TNM2027
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_price = Column(Numeric(18, 4), nullable=False)
    mark_to_market = Column(Numeric(18, 4), nullable=True)
    liquidity_bucket = Column(String(32), nullable=True)
    maturity_date = Column(Date, nullable=True)
    last_event = Column(Date, nullable=True)

    customer = relationship("CustomerCore")


class InvestmentMovement(Base):
    """Movement (transaction) affecting an investment position.

    Represents buy/sell orders, reinvestments and other events that change
    the quantity or valuation of an investment instrument. A movement may
    refer to any instrument and is linked to a customer.
    """

    __tablename__ = "investment_movements"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    instrument_id = Column(String(64), nullable=False)
    movement_type = Column(String(32), nullable=False)  # e.g. buy, sell, dividend
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    transaction_date = Column(Date, nullable=False)
    settlement_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("CustomerCore")


class FxOperation(Base):
    """Foreign exchange operation executed by a customer.

    Stores details of FX transactions, including the currency pair, the notional
    amount, the nature of the transaction (e.g. purchase, sale) and the
    settlement date. Refresh rate is daily.
    """

    __tablename__ = "fx_operations"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    currency_pair = Column(String(10), nullable=False)  # e.g. USD/BRL
    notional = Column(Numeric(18, 2), nullable=False)
    nature = Column(String(32), nullable=False)  # purchase, sale
    settlement_date = Column(Date, nullable=False)
    rate = Column(Numeric(10, 6), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("CustomerCore", back_populates="fx_operations")


class Consent(Base):
    """Consent granted by a customer for data sharing or payment initiation.

    This table records when a customer has granted a consent, which scopes
    (accounts, credit, investments, etc.) are covered, and when it expires.
    """

    __tablename__ = "consents"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)

    customer = relationship("CustomerCore", back_populates="consents")
    scopes = relationship("ConsentScope", back_populates="consent", cascade="all, delete-orphan")


class ConsentScope(Base):
    """Individual scope within a consent.

    Each scope specifies a domain (accounts, credit, investments, etc.)
    authorised for sharing. Scopes enable fine‑grained control over what
    data is accessible.
    """

    __tablename__ = "consent_scopes"

    id = Column(Integer, primary_key=True)
    consent_id = Column(Integer, ForeignKey("consents.id", ondelete="CASCADE"), nullable=False)
    scope = Column(String(32), nullable=False)  # accounts, credit, investments, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    consent = relationship("Consent", back_populates="scopes")


class PaymentOrder(Base):
    """Payment order initiated via Open Finance (e.g. PIX).

    Represents an order to transfer funds initiated by the customer through
    an initiator of payment service provider (PTI). Includes the unique
    identifier of the payment (e.g. PIX E2E), status and timestamps.
    """

    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer_core.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    scope = Column(String(32), nullable=False)  # accounts, credit, investments, etc.
    pix_e2e_id = Column(String(50), nullable=True)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    customer = relationship("CustomerCore", back_populates="payment_orders")
