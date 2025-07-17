import React from 'react';
import { 
  Container, 
  Typography, 
  Box, 
  Paper,
  Divider
} from '@mui/material';

const TermsOfService: React.FC = () => {
  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom align="center">
          Terms of Service
        </Typography>
        
        <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 4 }}>
          Last updated: {new Date().toLocaleDateString()}
        </Typography>

        <Divider sx={{ mb: 4 }} />

        <Box sx={{ '& > *': { mb: 3 } }}>
          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              1. Acceptance of Terms
            </Typography>
            <Typography variant="body1" paragraph>
              By accessing and using PriceAdjustPro ("the Service"), you accept and agree to be bound by the terms and provision of this agreement. If you do not agree to abide by the above, please do not use this service.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              2. Description of Service
            </Typography>
            <Typography variant="body1" paragraph>
              PriceAdjustPro is a web application designed to help Costco shoppers track their receipts and identify potential price adjustment opportunities by comparing purchase prices with current promotions and sales.
            </Typography>
            <Typography variant="body1" paragraph>
              The Service includes:
            </Typography>
            <Typography variant="body1" component="div">
              • Receipt upload and processing capabilities
              • AI-powered receipt parsing and data extraction
              • Price comparison and adjustment opportunity identification
              • Analytics and reporting features
              • Promotional sale tracking
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              3. User Accounts and Registration
            </Typography>
            <Typography variant="body1" paragraph>
              To access certain features of the Service, you must register for an account. You agree to:
            </Typography>
            <Typography variant="body1" component="div">
              • Provide accurate, current, and complete information during registration
              • Maintain and update your account information
              • Keep your password secure and confidential
              • Accept responsibility for all activities under your account
              • Notify us immediately of any unauthorized use of your account
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              4. User Responsibilities and Prohibited Uses
            </Typography>
            <Typography variant="body1" paragraph>
              You agree not to use the Service to:
            </Typography>
            <Typography variant="body1" component="div">
              • Upload false, misleading, or fraudulent receipt information
              • Violate any applicable laws or regulations
              • Infringe upon the rights of others
              • Upload malicious software or content
              • Attempt to gain unauthorized access to our systems
              • Use automated tools to access the Service without permission
              • Share your account credentials with others
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              5. Receipt Data and Content
            </Typography>
            <Typography variant="body1" paragraph>
              You retain ownership of the receipt data you upload. By using the Service, you grant us a limited license to:
            </Typography>
            <Typography variant="body1" component="div">
              • Process and analyze your receipt data to provide the Service
              • Store your data securely on our servers
              • Use aggregated, anonymized data for service improvement
            </Typography>
            <Typography variant="body1" paragraph sx={{ mt: 2 }}>
              You are responsible for ensuring that any receipt data you upload does not violate the privacy or rights of others.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              6. Service Availability and Modifications
            </Typography>
            <Typography variant="body1" paragraph>
              We strive to provide reliable service but cannot guarantee 100% uptime. We reserve the right to:
            </Typography>
            <Typography variant="body1" component="div">
              • Modify, suspend, or discontinue the Service at any time
              • Update these terms of service with notice to users
              • Implement new features or remove existing ones
              • Perform maintenance that may temporarily affect service availability
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              7. Accuracy and Disclaimers
            </Typography>
            <Typography variant="body1" paragraph>
              While we strive for accuracy in our price adjustment recommendations:
            </Typography>
            <Typography variant="body1" component="div">
              • We cannot guarantee the accuracy of receipt parsing or price comparisons
              • Users should verify all information before taking action
              • We are not responsible for decisions made based on our recommendations
              • Costco's price adjustment policies may change without notice
              • Final approval of price adjustments is at Costco's discretion
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              8. Subscription and Payment Terms
            </Typography>
            <Typography variant="body1" paragraph>
              For paid subscription services:
            </Typography>
            <Typography variant="body1" component="div">
              • Subscription fees are billed in advance
              • Cancellation takes effect at the end of the current billing period
              • No refunds for partial months unless required by law
              • We may change subscription pricing with 30 days notice
              • Failed payments may result in service suspension
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              9. Limitation of Liability
            </Typography>
            <Typography variant="body1" paragraph>
              To the maximum extent permitted by law, PriceAdjustPro shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the Service, including but not limited to loss of profits, data, or business opportunities.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              10. Privacy and Data Protection
            </Typography>
            <Typography variant="body1" paragraph>
              Your privacy is important to us. Our collection and use of personal information is governed by our Privacy Policy, which is incorporated into these terms by reference.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              11. Termination
            </Typography>
            <Typography variant="body1" paragraph>
              Either party may terminate this agreement at any time. Upon termination:
            </Typography>
            <Typography variant="body1" component="div">
              • Your access to the Service will be suspended
              • You may request deletion of your account and data
              • Certain provisions of these terms will survive termination
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              12. Governing Law
            </Typography>
            <Typography variant="body1" paragraph>
              These terms shall be governed by and construed in accordance with the laws of the jurisdiction in which PriceAdjustPro operates, without regard to conflict of law provisions.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              13. Changes to Terms
            </Typography>
            <Typography variant="body1" paragraph>
              We reserve the right to modify these terms at any time. Material changes will be communicated to users via email or through the Service. Continued use of the Service after changes constitutes acceptance of the new terms.
            </Typography>
          </Box>

          <Box>
            <Typography variant="h5" component="h2" gutterBottom>
              14. Contact Information
            </Typography>
            <Typography variant="body1" paragraph>
              If you have any questions about these Terms of Service, please contact us at:
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

export default TermsOfService;