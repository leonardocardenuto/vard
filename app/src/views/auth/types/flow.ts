export type AuthStep = 'landing' | 'email' | 'password' | 'signup';

export type SignupForm = {
  avatarUrl: string;
  birthDateIso: string;
  firstName: string;
  lastName: string;
  birthDate: string;
  password: string;
  confirmPassword: string;
};

export const initialSignupForm: SignupForm = {
  avatarUrl: '',
  birthDateIso: '',
  firstName: '',
  lastName: '',
  birthDate: '',
  password: '',
  confirmPassword: '',
};

export const AUTH_GRADIENT_COLORS = ['#03CDF4', '#019BDE', '#01EBD0'] as const;
export const AUTH_GRADIENT_LOCATIONS = [0.08, 0.48, 1] as const;
