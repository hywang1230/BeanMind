export function currentMonth() {
  const today = new Date()
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
}

// Accept legacy date links while keeping report filters at month granularity.
export function reportMonth(value: unknown) {
  const month = String(value || '').slice(0, 7)
  if (!/^(20\d{2}|2100)-(0[1-9]|1[0-2])$/.test(month)) return currentMonth()
  return month
}

export function monthStart(month: string) {
  return `${month}-01`
}

export function monthEnd(month: string) {
  const [year, number] = month.split('-').map(Number)
  const day = new Date(year!, number!, 0).getDate()
  return `${month}-${String(day).padStart(2, '0')}`
}
