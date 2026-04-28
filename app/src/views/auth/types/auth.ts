export type AuthMode = 'login' | 'signup';

export type AuthFormState = {
  fullName: string;
  email: string;
  phone: string;
  password: string;
};

export type AuthFormErrors = Partial<Record<keyof AuthFormState, string>>;

export const initialAuthFormState: AuthFormState = {
  fullName: '',
  email: '',
  phone: '',
  password: '',
};
