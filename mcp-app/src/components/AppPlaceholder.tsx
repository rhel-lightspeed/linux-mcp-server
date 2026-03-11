export function AppPlaceholder() {
  return (
    <div className="flex justify-center items-center min-h-[200px]">
      <div className="flex items-center">
        <span className="relative flex size-3 mr-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-app-fg-warning opacity-75"></span>
          <span className="relative inline-flex size-3 rounded-full bg-app-bg-warning"></span>
        </span>
        <span>Waiting for the detail information...</span>
      </div>
    </div>
  );
}
