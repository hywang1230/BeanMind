import apiClient from './client'

export type ExchangeRate = {
    currency: string          // 源货币代码（如 USD）
    rate: string              // 汇率
    quote_currency: string    // 目标货币（主货币，如 CNY）
    effective_date: string    // 生效日期
    currency_pair: string     // 货币对（如 USD/CNY）
}

export type ExchangeRateListResponse = {
    exchange_rates: ExchangeRate[]
    total: number
}

export type CurrencyListResponse = {
    currencies: string[]
    total: number
}

export type CreateExchangeRateRequest = {
    currency: string
    rate: string
    quote_currency?: string
    effective_date?: string
}

export type UpdateExchangeRateRequest = {
    rate: string
}

export type ConvertAmountRequest = {
    amount: string
    from_currency: string
    to_currency: string
    as_of_date?: string
}

export type ConvertAmountResponse = {
    original_amount: string
    converted_amount: string
    from_currency: string
    to_currency: string
}

export const exchangeRatesApi = {
    /**
     * 获取所有汇率列表
     * @param quoteCurrency 目标货币（主货币），默认 CNY
     */
    async getExchangeRates(quoteCurrency: string = 'CNY'): Promise<ExchangeRate[]> {
        const response: ExchangeRateListResponse = await apiClient.get('/api/exchange-rates', {
            params: { quote_currency: quoteCurrency }
        })
        return response.exchange_rates
    },

    /**
     * 获取指定货币的最新汇率
     * @param currency 源货币代码
     * @param quoteCurrency 目标货币（主货币）
     */
    async getExchangeRate(currency: string, quoteCurrency: string = 'CNY'): Promise<ExchangeRate> {
        return apiClient.get(`/api/exchange-rates/${currency}`, {
            params: { quote_currency: quoteCurrency }
        })
    },

    /**
     * 获取指定货币的历史汇率
     * @param currency 源货币代码
     * @param quoteCurrency 目标货币（主货币）
     */
    async getExchangeRateHistory(currency: string, quoteCurrency: string = 'CNY'): Promise<ExchangeRate[]> {
        const response: ExchangeRateListResponse = await apiClient.get(`/api/exchange-rates/${currency}/history`, {
            params: { quote_currency: quoteCurrency }
        })
        return response.exchange_rates
    },

    /**
     * 创建汇率
     */
    createExchangeRate(data: CreateExchangeRateRequest): Promise<ExchangeRate> {
        return apiClient.post('/api/exchange-rates', data)
    },

    /**
     * 更新汇率
     * @param currency 源货币代码
     * @param effectiveDate 生效日期
     * @param data 更新数据
     * @param quoteCurrency 目标货币（主货币）
     */
    updateExchangeRate(
        currency: string,
        effectiveDate: string,
        data: UpdateExchangeRateRequest,
        quoteCurrency: string = 'CNY'
    ): Promise<ExchangeRate> {
        return apiClient.put(`/api/exchange-rates/${currency}/${effectiveDate}`, data, {
            params: { quote_currency: quoteCurrency }
        })
    },

    /**
     * 删除汇率
     * @param currency 源货币代码
     * @param effectiveDate 生效日期
     * @param quoteCurrency 目标货币（主货币）
     */
    deleteExchangeRate(
        currency: string,
        effectiveDate: string,
        quoteCurrency: string = 'CNY'
    ): Promise<{ message: string }> {
        return apiClient.delete(`/api/exchange-rates/${currency}/${effectiveDate}`, {
            params: { quote_currency: quoteCurrency }
        })
    },

    /**
     * 获取常用货币代码列表
     */
    async getCommonCurrencies(): Promise<string[]> {
        const response: CurrencyListResponse = await apiClient.get('/api/exchange-rates/currencies/common')
        return response.currencies
    },

    /**
     * 获取所有已定义汇率的货币代码
     */
    async getAvailableCurrencies(): Promise<string[]> {
        const response: CurrencyListResponse = await apiClient.get('/api/exchange-rates/currencies/available')
        return response.currencies
    },

    /**
     * 货币换算
     */
    convertAmount(data: ConvertAmountRequest): Promise<ConvertAmountResponse> {
        return apiClient.post('/api/exchange-rates/convert', data)
    }
}
