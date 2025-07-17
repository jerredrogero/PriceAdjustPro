import React from 'react';
import { 
  Container, 
  Typography, 
  Box, 
  Paper,
  Divider
} from '@mui/material';

const PrivacyPolicy: React.FC = () => {
  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom align="center">
          Privacy Policy
        </Typography>
        
        <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 4 }}>
          Last updated: {new Date().toLocaleDateString()}
        </Typography>

        <Divider sx={{ mb: 4 }} />

        <Box sx={{ '& > *': { mb: 3 } }}>
          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              1. Information We Collect
            </Typography>
            <Typography variant="body1" paragraph>
              We collect information you provide directly to us, such as when you create an account, upload receipts, or contact us for support.
            </Typography>
            <Typography variant="h6" component="h3" gutterBottom sx={{ mt: 2 }}>
              Personal Information
            </Typography>
            <Typography variant="body1" paragraph>
              • Account information (username, email address, password)
              • Profile information (first name, last name)
              • Communication preferences
            </Typography>
            <Typography variant="h6" component="h3" gutterBottom sx={{ mt: 2 }}>
              Receipt Data
            </Typography>
            <Typography variant="body1" paragraph>
              • Receipt images and PDF files you upload
              • Transaction details extracted from receipts (store location, purchase date, item descriptions, prices)
              • Manual edits and corrections you make to receipt data
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              2. How We Use Your Information
            </Typography>
            <Typography variant="body1" paragraph>
              We use the information we collect to:
            </Typography>
            <Typography variant="body1" component="div">
              • Provide, maintain, and improve our services
              • Process and analyze your receipts to identify price adjustment opportunities
              • Send you notifications about potential savings and price adjustments
              • Respond to your questions and provide customer support
              • Protect against fraud and abuse
              • Comply with legal obligations
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              3. Information Sharing
            </Typography>
            <Typography variant="body1" paragraph>
              We do not sell, trade, or otherwise transfer your personal information to third parties except in the following circumstances:
            </Typography>
            <Typography variant="body1" component="div">
              • With your explicit consent
              • To comply with legal requirements or court orders
              • To protect our rights, property, or safety, or that of our users
              • In connection with a business transfer or acquisition
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              4. Data Security
            </Typography>
            <Typography variant="body1" paragraph>
              We implement appropriate technical and organizational measures to protect your personal information against unauthorized access, alteration, disclosure, or destruction. However, no method of transmission over the internet or electronic storage is 100% secure.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              5. Data Retention
            </Typography>
            <Typography variant="body1" paragraph>
              We retain your personal information for as long as necessary to provide our services and fulfill the purposes outlined in this policy, unless a longer retention period is required by law.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              6. Your Rights
            </Typography>
            <Typography variant="body1" paragraph>
              Depending on your location, you may have certain rights regarding your personal information, including:
            </Typography>
            <Typography variant="body1" component="div">
              • Right to access your personal information
              • Right to correct inaccurate information
              • Right to delete your personal information
              • Right to restrict or object to processing
              • Right to data portability
            </Typography>
            <Typography variant="body1" paragraph sx={{ mt: 2 }}>
              To exercise these rights, please contact us using the information provided below.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              7. Cookies and Tracking
            </Typography>
            <Typography variant="body1" paragraph>
              We use cookies and similar tracking technologies to enhance your experience, analyze usage patterns, and improve our services. You can control cookie settings through your browser preferences.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              8. Children's Privacy
            </Typography>
            <Typography variant="body1" paragraph>
              Our services are not intended for children under 13 years of age. We do not knowingly collect personal information from children under 13.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              9. Changes to This Policy
            </Typography>
            <Typography variant="body1" paragraph>
              We may update this privacy policy from time to time. We will notify you of any material changes by posting the new policy on this page and updating the "Last updated" date.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              10. Contact Us
            </Typography>
            <Typography variant="body1" paragraph>
              If you have any questions about this privacy policy or our data practices, please contact us at:
            </Typography>
            <Typography variant="body1" component="div">
              Email: support@priceadjustpro.com<br />
              Website: https://priceadjustpro.com
            </Typography>
          </Box>
        </Box>
      </Paper>
    </Container>
  );
};

export default PrivacyPolicy;