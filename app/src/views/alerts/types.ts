export type AlertItem = {
  id: string;
  title: string;
  kind: "fall" | "fight" | "general";
  room: string;
  time: string;
  precision: number;
  imageUrl: string;
  isValidationAnswered: boolean;
  payload: Record<string, unknown>;
};

export type AlertsStackParamList = {
  AlertsList: {
    accessToken: string;
  };
  AlertDetails: {
    alert: AlertItem;
    accessToken: string;
  };
};
