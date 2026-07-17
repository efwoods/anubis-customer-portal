# Local development image only — the production client deploys to Vercel.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5171

CMD ["npm", "run", "dev", "--", "--host"]
