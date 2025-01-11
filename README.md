Question 2
I need to create backend in express.js for a Blood Bank
the following are the endpoints that need to be created. Use mongodb for the database and create the schemas according to the details i provide

the endpoints are divided by roles 

All roles
/api/auth/login POST user login
/api/auth/register POST user registration
/api/auth/profile GET get user profile
/api/auth/profile PATCH update profile

Donor
/api/donors/donations POST create donation
/api/donors/donations GET get donation history
/api/donors/eligibility GET check eligibility

Recipient 
/api/recipients/requests POST create blood request
/api/recipients/requests GET get request history
/api/recipients/requests/:id PATCH update request

Staff 


