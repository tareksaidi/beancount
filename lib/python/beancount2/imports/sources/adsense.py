#!/usr/bin/env python
"""
Interpret the Google AdSense CSV file and output transactions in a format
suitable for Ledger.
"""

import re, time, codecs
import datetime
from decimal import Decimal
from itertools import count
from collections import namedtuple

from beancount2.core import data
from beancount2.core.data import to_decimal
from beancount2.core.data import Transaction, Check, Posting, Amount
from beancount2.utils import csv_tuple_reader, DateIntervalTicker
from beancount2.imports import imports


CONFIG = {
    'FILE'          : 'Account for filing',
    'cash_currency' : 'USD',
    'cash'          : 'Main account holding the funds',
    'income'        : 'Income account',
    'transfer'      : 'Default account where money gets transferred to',
}


#### FIXME: This is incomplete, I need to finish porting this one (this is the last one).

def import_file(filename, config):
    """Import a Google AdSense file."""

    config = imports.module_config_accountify(config)
    new_entries = []

    currency = config['cash_currency']
    payee = "Google AdSense"

    ticker = DateIntervalTicker(
        lambda date: ((date.year * 12 + (date.month - 1)) // 3))
    prev_row = None

    f = open(filename, "r", encoding='utf-16')
    for index, row in enumerate(csv_tuple_reader(f, delimiter='\t')):

        # Convert the datatypes.
        row = row._replace(
            date = datetime.datetime.strptime(row.date, '%m/%d/%y').date(),
            amount = to_decimal(row.amount),
            account_balance = to_decimal(row.account_balance))

        fileloc = data.FileLocation(filename, index)

        # Insert some Check entries every 3 months or so.
        n3mths = (row.date.year * 12 + row.date.month) // 3

        if ticker.check(row.date):
            if prev_row:
                check = Check(fileloc, row.date, config['cash'],
                              Amount(prev_row.account_balance, currency), None)
                new_entries.append(check)
        prev_row = row

        entry = Transaction(fileloc, row.date, data.FLAG_IMPORT, payee, row.description, None, None, [])

        if row.description == 'Payment issued':
            data.create_simple_posting(entry, config['cash'], row.amount, currency)
            data.create_simple_posting(entry, config['transfer'], -row.amount, currency)

        elif row.description.startswith('Earnings '):
            data.create_simple_posting(entry, config['cash'], row.amount, currency)
            data.create_simple_posting(entry, config['income'], -row.amount, currency)

        elif row.description.startswith('EFT not successful - earnings credited back'):
            data.create_simple_posting(entry, config['cash'], row.amount, currency)
            data.create_simple_posting(entry, config['transfer'], -row.amount, currency)

        else:
            raise ValueError('Unknown row type: {}'.format(row))

        new_entries.append(entry)

    check = Check(fileloc, row.date + datetime.timedelta(days=1), config['cash'],
                  Amount(row.account_balance, currency), None)
    new_entries.append(check)

    return new_entries


debug = False