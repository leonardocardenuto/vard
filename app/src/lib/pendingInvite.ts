let _token: string | null = null;

export const pendingInvite = {
  get: (): string | null => _token,
  set: (token: string): void => {
    _token = token;
  },
  clear: (): void => {
    _token = null;
  },
};
