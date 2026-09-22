export default function Banner({ kind = "error", children }: { kind?: "error" | "info" | "success"; children: React.ReactNode }) {
  const styles = { error: "bg-coral-500/10 text-coral-500 border-coral-500/20",
    info: "bg-navy-900/5 text-navy-900/70 border-navy-900/10", success: "bg-teal-500/10 text-teal-700 border-teal-500/20" };
  return <div className={`rounded-md border px-3 py-2 text-sm ${styles[kind]}`}>{children}</div>;
}
