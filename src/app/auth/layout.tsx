/** Gives every sign-in / sign-up page a main landmark for screen readers. */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <main>{children}</main>;
}
