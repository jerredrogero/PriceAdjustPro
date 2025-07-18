import React from 'react';
import { 
  Container, 
  Typography, 
  Box, 
  Paper,
  Divider,
  Button,
  Grid,
  Card,
  CardContent
} from '@mui/material';
import {
  Email as EmailIcon,
  Help as HelpIcon,
  QuestionAnswer as FAQIcon,
  ReportProblem as BugIcon
} from '@mui/icons-material';

const Support: React.FC = () => {
  const handleEmailSupport = () => {
    window.location.href = 'mailto:support@priceadjustpro.com?subject=Support Request - PriceAdjustPro';
  };

  const supportTopics = [
    {
      icon: <HelpIcon color="primary" sx={{ fontSize: 40 }} />,
      title: "General Questions",
      description: "Need help understanding how PriceAdjustPro works or have questions about features?",
    },
    {
      icon: <BugIcon color="error" sx={{ fontSize: 40 }} />,
      title: "Technical Issues",
      description: "Experiencing problems with receipt uploads, account access, or app functionality?",
    },
    {
      icon: <FAQIcon color="success" sx={{ fontSize: 40 }} />,
      title: "Account & Billing",
      description: "Questions about your subscription, billing, or account settings?",
    }
  ];

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Typography variant="h3" component="h1" gutterBottom>
            Support Center
          </Typography>
          <Typography variant="h6" color="text.secondary" paragraph>
            We're here to help! Get in touch with our support team for assistance.
          </Typography>
        </Box>

        <Divider sx={{ mb: 4 }} />

        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Typography variant="h5" component="h2" gutterBottom>
            Contact Support
          </Typography>
          <Typography variant="body1" paragraph sx={{ mb: 3 }}>
            For the fastest response, please email us directly with your question or issue.
            Our support team typically responds within 24 hours during business days.
          </Typography>
          
          <Button
            variant="contained"
            size="large"
            startIcon={<EmailIcon />}
            onClick={handleEmailSupport}
            sx={{ 
              py: 1.5, 
              px: 4,
              fontSize: '1.1rem',
              textTransform: 'none'
            }}
          >
            Email Support Team
          </Button>
          
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            support@priceadjustpro.com
          </Typography>
        </Box>

        <Divider sx={{ mb: 4 }} />

        <Box sx={{ mb: 4 }}>
          <Typography variant="h5" component="h2" gutterBottom align="center" sx={{ mb: 3 }}>
            What can we help you with?
          </Typography>
          
          <Grid container spacing={3}>
            {supportTopics.map((topic, index) => (
              <Grid item xs={12} md={4} key={index}>
                <Card 
                  sx={{ 
                    height: '100%', 
                    display: 'flex', 
                    flexDirection: 'column',
                    textAlign: 'center',
                    transition: 'transform 0.2s',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: 3
                    }
                  }}
                >
                  <CardContent sx={{ flexGrow: 1, p: 3 }}>
                    <Box sx={{ mb: 2 }}>
                      {topic.icon}
                    </Box>
                    <Typography variant="h6" component="h3" gutterBottom>
                      {topic.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {topic.description}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>

        <Divider sx={{ mb: 4 }} />

        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="h6" component="h3" gutterBottom>
            When contacting support, please include:
          </Typography>
          <Grid container spacing={2} sx={{ mt: 2 }}>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary">
                • Your account email address
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • Description of the issue
              </Typography>
            </Grid>
            <Grid item xs={12} sm={6}>
              <Typography variant="body2" color="text.secondary">
                • Steps you've already tried
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • Screenshots (if applicable)
              </Typography>
            </Grid>
          </Grid>
        </Box>

        <Box sx={{ mt: 4, p: 3, backgroundColor: 'action.hover', borderRadius: 2 }}>
          <Typography variant="body2" color="text.secondary" align="center">
            <strong>Business Hours:</strong> Monday - Friday, 9:00 AM - 5:00 PM PST<br />
            We aim to respond to all support requests within 24 hours during business days.
          </Typography>
        </Box>
      </Paper>
    </Container>
  );
};

export default Support;