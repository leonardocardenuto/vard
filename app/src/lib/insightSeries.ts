export function buildIncidentSeries(
  notifications: Array<{ created_at: string }>,
  startTime: number,
  endTime: number,
): Array<{ label: string; value: number }> {
  const start = new Date(startTime);
  start.setHours(0, 0, 0, 0);
  const dates: number[] = [];
  for (const day = new Date(start); day.getTime() <= endTime; day.setDate(day.getDate() + 1)) dates.push(day.getTime());
  const series = dates.map((timestamp) => ({ label: new Date(timestamp).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }), value: 0 }));
  notifications.forEach((notification) => {
    const createdAt = Date.parse(notification.created_at);
    if (!Number.isFinite(createdAt) || createdAt < startTime || createdAt > endTime) return;
    const index = dates.findIndex((timestamp, i) => createdAt >= timestamp && (i === dates.length - 1 || createdAt < dates[i + 1]));
    if (index >= 0) series[index].value += 1;
  });
  return series;
}

