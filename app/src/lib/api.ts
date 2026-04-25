type AuthPayload = {
  email: string;
  password: string;
};

type RegisterPayload = AuthPayload & {
  full_name?: string;
  phone?: string;
};

type TokenResponse = {
  access_token: string;
  token_type: string;
};

type UserResponse = {
  id: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
};

type ValidationDetailItem = {
  loc?: Array<string | number>;
  msg?: string;
};

type ApiErrorPayload = {
  detail?: string | ValidationDetailItem[];
};

const API_BASE_URL = 'http://185.135.137.249:8000';

export class ApiRequestError extends Error {
  fieldErrors?: Record<string, string>;

  constructor(message: string, fieldErrors?: Record<string, string>) {
    super(message);
    this.name = 'ApiRequestError';
    this.fieldErrors = fieldErrors;
  }
}

function resolveApiBaseUrl() {
  return API_BASE_URL;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${resolveApiBaseUrl()}${path}`;
  let response: Response;

  try {
    response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch {
    throw new Error(`Não foi possível conectar com a API em ${url}.`);
  }

  if (!response.ok) {
    let message = 'Não foi possível completar a solicitação.';
    let fieldErrors: Record<string, string> | undefined;

    try {
      const errorPayload = (await response.json()) as ApiErrorPayload;
      if (errorPayload.detail) {
        const normalized = normalizeApiError(errorPayload.detail);
        message = normalized.message;
        fieldErrors = normalized.fieldErrors;
      }
    } catch {
      // keep fallback message
    }

    throw new ApiRequestError(message, fieldErrors);
  }

  return (await response.json()) as T;
}

function normalizeApiError(detail: ApiErrorPayload['detail']) {
  if (typeof detail === 'string') {
    const message = translateApiMessage(detail);
    return {
      message,
      fieldErrors: inferFieldErrorsFromMessage(detail, message),
    };
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const fieldErrors: Record<string, string> = {};
    const messages = detail.map((item) => {
      const field = item.loc?.[item.loc.length - 1];
      const translatedMessage = translateApiMessage(item.msg ?? 'Valor inválido.');

      if (typeof field === 'string') {
        fieldErrors[field] = translatedMessage;
        return `${humanizeField(field)}: ${translatedMessage}`;
      }

      return translatedMessage;
    });

    return {
      message: messages.join('\n'),
      fieldErrors,
    };
  }

  return {
    message: 'Não foi possível completar a solicitação.',
  };
}

function inferFieldErrorsFromMessage(rawMessage: string, translatedMessage: string) {
  const normalized = rawMessage.trim();

  if (normalized === 'Email already registered') {
    return { email: translatedMessage } as Record<string, string>;
  }

  if (normalized === 'Invalid credentials') {
    return {
      email: 'Confira seu e-mail.',
      password: 'Confira sua senha.',
    } as Record<string, string>;
  }

  return undefined;
}

function translateApiMessage(message: string) {
  const normalized = message.trim();

  const exactTranslations: Record<string, string> = {
    'Invalid credentials': 'Credenciais inválidas.',
    'Email already registered': 'Este e-mail já está cadastrado.',
    'String should have at least 8 characters': 'Deve ter pelo menos 8 caracteres.',
    'Field required': 'Campo obrigatório.',
    'Input should be a valid string': 'Valor inválido.',
    'Value error, Invalid access token': 'Token de acesso inválido.',
  };

  if (exactTranslations[normalized]) {
    return exactTranslations[normalized];
  }

  if (normalized.includes('value is not a valid email address')) {
    return 'Digite um e-mail válido.';
  }

  if (normalized.includes('An email address must have an @-sign')) {
    return 'Digite um e-mail válido.';
  }

  if (normalized.includes('password cannot be longer than 72 bytes')) {
    return 'Não foi possível processar sua senha.';
  }

  if (normalized.includes('String should have at least')) {
    const match = normalized.match(/at least (\d+) characters/);
    if (match) {
      return `Deve ter pelo menos ${match[1]} caracteres.`;
    }
  }

  if (normalized.includes('String should have at most')) {
    const match = normalized.match(/at most (\d+) characters/);
    if (match) {
      return `Deve ter no máximo ${match[1]} caracteres.`;
    }
  }

  return normalized;
}

function humanizeField(field: string) {
  const labels: Record<string, string> = {
    email: 'E-mail',
    password: 'Senha',
    full_name: 'Nome completo',
    phone: 'Telefone',
  };

  return labels[field] ?? field;
}

export async function login(payload: AuthPayload) {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function register(payload: RegisterPayload) {
  return request<TokenResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getMe(token: string) {
  return request<UserResponse>('/auth/me', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}
