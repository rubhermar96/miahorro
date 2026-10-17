// Sample data shaped like the API's responses, for page tests.

export const account = (fields: Record<string, unknown> = {}) => ({
  id: 'acc-1',
  name: 'Nómina',
  kind: 'checking',
  institution: 'Bankinter',
  iban_last4: '1234',
  currency: 'EUR',
  opening_balance: '1000.00',
  opening_date: '2026-01-01',
  is_joint: false,
  maturity_date: null,
  auto_renew: false,
  early_cancellation_note: null,
  balance: '1000.00',
  archived: false,
  current_rate: null,
  reserved: '0.00',
  ...fields,
  available: fields.available ?? fields.balance ?? '1000.00',
})

export const category = (fields: Record<string, unknown>) => ({
  parent_id: null,
  icon: null,
  archived: false,
  recent_uses: 0,
  kind: 'expense',
  ...fields,
})

export const categories = [
  category({ id: 'food', name: 'Alimentación', icon: '🛒' }),
  category({ id: 'groceries', name: 'Supermercado', parent_id: 'food', recent_uses: 1 }),
  category({ id: 'restaurants', name: 'Restaurantes', parent_id: 'food', recent_uses: 7 }),
  category({ id: 'transport', name: 'Transporte', icon: '🚗' }),
  category({ id: 'fuel', name: 'Combustible', parent_id: 'transport' }),
  category({ id: 'other', name: 'Otros gastos', icon: '📦' }),
  category({ id: 'salary', name: 'Nómina', kind: 'income', icon: '💼', recent_uses: 1 }),
]

export const transaction = (fields: Record<string, unknown> = {}) => ({
  id: 'tx-1',
  account_id: 'acc-1',
  date: '2026-10-15',
  kind: 'expense',
  amount: '-45.20',
  description: 'Mercadona',
  category_id: 'groceries',
  note: null,
  tags: [],
  transfer_id: null,
  source: 'manual',
  created_at: '2026-10-15T10:00:00Z',
  ...fields,
})

export const page = (items: unknown[], fields: Record<string, unknown> = {}) => ({
  items,
  total: items.length,
  income: '0.00',
  expenses: '0.00',
  ...fields,
})
