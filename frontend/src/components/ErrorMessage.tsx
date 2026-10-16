export function ErrorMessage({ message }: { message: string | null }) {
  return message ? (
    <p className="alert" role="alert">
      {message}
    </p>
  ) : null
}
