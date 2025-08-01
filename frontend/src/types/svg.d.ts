declare module '*.svg' {
  const content: string;
  export default content;
}

declare module '*.svg?url' {
  const content: string;
  export default content;
}

declare module '*.svg?inline' {
  const content: React.FunctionComponent<React.SVGProps<SVGSVGElement>>;
  export default content;
} 