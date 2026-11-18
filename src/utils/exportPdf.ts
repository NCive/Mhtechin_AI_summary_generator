export function exportToBrowserPdf(title?: string): void {
  const originalTitle = document.title;
  if (title) {
    document.title = `${title} - Chatmeet Summary`;
  }

  // Trigger browser print to PDF dialog
  window.print();

  // Reset title
  setTimeout(() => {
    document.title = originalTitle;
  }, 1000);
}
