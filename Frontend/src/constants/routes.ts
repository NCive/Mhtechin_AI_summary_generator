export const ROUTES = {
  HOME: '/',
  MEETING_DETAILS: '/meetings/:id',
  MEETING_DETAILS_PATH: (id: string) => `/meetings/${id}`,
} as const;
