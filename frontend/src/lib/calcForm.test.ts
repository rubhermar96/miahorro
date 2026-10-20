import { describe, expect, it } from 'vitest'

import i18n from '../i18n'
import { amountText, fromBody, type SectionSpec, toBody } from './calcForm'

const t = i18n.t.bind(i18n)

const sections: SectionSpec[] = [
  {
    fields: [
      { key: 'price', kind: 'amount', label: 'calc.f.price' },
      { key: 'rate', kind: 'rate', label: 'calc.f.tin' },
      { key: 'years', kind: 'int', label: 'calc.f.termYears' },
      { key: 'extra', kind: 'amount', label: 'calc.f.notary', optional: true },
      { key: 'new_build', kind: 'check', label: 'calc.f.newBuild' },
      {
        key: 'only_new',
        kind: 'rate',
        label: 'calc.f.agency',
        when: (own) => own.new_build === true,
      },
      {
        kind: 'list',
        key: 'offers',
        item: 'calc.mortgage.offer',
        add: 'calc.mortgage.addOffer',
        min: 1,
        max: 3,
        blank: (index) => ({ name: `Oferta ${index + 1}`, tin: '' }),
        fields: [
          { key: 'name', kind: 'text', label: 'calc.f.name' },
          { key: 'tin', kind: 'rate', label: 'calc.f.tin' },
        ],
      },
    ],
  },
]

const values = {
  price: '200.000',
  rate: '2,5',
  years: '30',
  extra: '',
  new_build: false,
  only_new: '9',
  offers: [{ name: 'Banco', tin: '3' }],
}

describe('calculator forms', () => {
  it('turns typed text into the API body', () => {
    expect(toBody(sections, values, t)).toEqual({
      body: {
        price: '200000.00',
        rate: '2.5',
        years: 30,
        new_build: false,
        offers: [{ name: 'Banco', tin: '3' }],
      },
    })
  })

  it('sends fields that only apply in some cases when they do', () => {
    const result = toBody(sections, { ...values, new_build: true }, t)
    expect(result).toMatchObject({ body: { new_build: true, only_new: '9' } })
  })

  it('names the first field to fix', () => {
    expect(toBody(sections, { ...values, price: '' }, t)).toEqual({
      error: 'Rellena «Precio de la vivienda (€)».',
    })
    expect(toBody(sections, { ...values, rate: 'dos' }, t)).toEqual({
      error: 'Revisa «TIN (%)»: no es un número válido.',
    })
    expect(toBody(sections, { ...values, offers: [{ name: 'Banco', tin: '' }] }, t)).toEqual({
      error: 'Rellena «TIN (%)».',
    })
  })

  it('reopens a saved body as typed text', () => {
    const body = {
      price: '200000.00',
      rate: '2.5000',
      years: 30,
      new_build: true,
      offers: [{ name: 'Banco', tin: '3.1000' }],
    }
    const reopened = fromBody(sections, body, { ...values, extra: '' })

    expect(reopened).toMatchObject({
      price: '200000',
      rate: '2,5',
      years: '30',
      new_build: true,
      extra: '',
      offers: [{ name: 'Banco', tin: '3,1' }],
    })
  })

  it('writes amounts the way people type them', () => {
    expect(amountText('1000.00')).toBe('1000')
    expect(amountText('1234.50')).toBe('1234,50')
  })
})
