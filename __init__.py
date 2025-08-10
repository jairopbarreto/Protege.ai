# Protege.ai data model package

"""
This package contains SQLAlchemy model definitions for the Protege.ai platform.

The models here are structured around the domain-driven architecture described in
the Open Finance data model. They include core entities such as customers,
accounts, cards, credit operations, investment positions, foreign exchange
operations, consents and payment orders.

Each model corresponds to a database table and defines the columns and
relationships necessary to store and query financial data pulled from Open
Finance APIs. These models are designed to be independent of any specific
framework and can be used with any SQLAlchemy-compatible database.

To use these models, import ``Base`` and the individual classes from
``protege_ai.models`` and use SQLAlchemy's ``create_all`` to create the
necessary tables.

Example:

.. code-block:: python

   from protege_ai.models import Base, CustomerCore, Account
   from sqlalchemy import create_engine

   engine = create_engine("sqlite:///protege_ai.db")
   Base.metadata.create_all(engine)

"""

from .models import (
    Base,
    CustomerCore,
    CustomerContact,
    Account,
    AccountBalance,
    AccountTransaction,
    Card,
    CardInvoice,
    CardTransaction,
    CreditContract,
    CreditSchedule,
    Collateral,
    PositionFund,
    PositionFixedIncome,
    PositionEquity,
    PositionTreasury,
    InvestmentMovement,
    FxOperation,
    Consent,
    ConsentScope,
    PaymentOrder,
)

__all__ = [
    "Base",
    "CustomerCore",
    "CustomerContact",
    "Account",
    "AccountBalance",
    "AccountTransaction",
    "Card",
    "CardInvoice",
    "CardTransaction",
    "CreditContract",
    "CreditSchedule",
    "Collateral",
    "PositionFund",
    "PositionFixedIncome",
    "PositionEquity",
    "PositionTreasury",
    "InvestmentMovement",
    "FxOperation",
    "Consent",
    "ConsentScope",
    "PaymentOrder",
]