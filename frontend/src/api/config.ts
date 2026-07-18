import apiClient from './client'

export type PublicConfig = {
  single_machine: boolean
  backup_managed_externally: boolean
  recurring_enabled: boolean
  llm_enabled: boolean
  llm_model: string | null
}

export const configApi = {
  get(): Promise<PublicConfig> {
    return apiClient.get('/api/config')
  },
}
