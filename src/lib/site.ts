/** Site-wide details used by the footer, legal pages and contact page.
 *  Set NEXT_PUBLIC_SUPPORT_EMAIL on Vercel to the inbox that should get
 *  customer messages (the default only works once that mailbox exists). */
export const SITE = {
  name: "ProductSpy Pro",
  url: "https://productspy.pro",
  company: "Chengdu Beiyanxinghe Technology Co., Ltd.",
  supportEmail: process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "support@productspy.pro",
  updated: "October 25, 2026",
};
