# ChatMeet Frontend

React 18, TypeScript, and Tailwind CSS client for the ChatMeet AI Meeting Intelligence platform.

---

## Features

- **Dashboard:** Meeting list with status indicators (`pending`, `processing`, `done`, `failed`), search, and sorting.
- **Upload Flow:** Drag-and-drop audio/video uploads with real-time validation and progress tracking.
- **Live Meeting View:** Live meeting sync with animated indicators, active speaker tracking, and real-time transcript streaming.
- **Meeting Detail:**
  - Executive Overview & Notes
  - Action Items with completion check toggles
  - Key Decisions, Project Progress, Challenges, and Next Steps
  - Interactive Q&A chat grounded directly in transcript timestamps
  - Speaker talk-time distribution analytics
  - Multi-format transcript & notes export (TXT, SRT, VTT, JSON)

---

## Tech Stack

- **Framework:** React 18
- **Language:** TypeScript
- **Build Tool:** Vite
- **Styling:** Tailwind CSS, PostCSS, Autoprefixer
- **Icons:** Lucide React
- **HTTP Client:** Axios
- **Routing:** React Router DOM (v6)

---

## Setup & Development

1. Navigate to `Frontend/`:
   ```bash
   cd Frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment settings:
   ```bash
   cp .env.example .env
   ```

4. Start development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

---

## Available Scripts

- `npm run dev`: Starts the local development server with Vite hot module replacement (HMR).
- `npm run build`: Type-checks with `tsc` and compiles optimized production assets into `dist/`.
- `npm run preview`: Locally previews the production build.
