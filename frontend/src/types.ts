/** Describe the minimal shared API response contracts. */
export interface HealthResponse {
  status: 'ok';
}

/** Describe a safe API error response. */
export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    field_errors?: Array<{ field: string; message: string }>;
  };
  request_id: string;
}
